# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution. See NOTICE at repository root.
"""
Service API for the ROBBO personal account (LK): its server reads a user's LMS notifications and
marks them read, so LK shows them in its own bell. The LMS stays the only store: «прочитано» in LK
is the same «прочитано» as in the LMS bell and feed. Texts come from robbo_texts.py, as in emails.

Callers: users named in ROBBO_NOTIFICATIONS_SERVICE_USERS (empty = the API is off), authenticated
with an OAuth2 client-credentials token (JWT or plain Bearer). They act for any ``user_id``, so the
LK service account must be used for nothing else.

    GET  /api/robbo/v1/notifications/service/feed/?user_id=&limit=&before=&lang=
         {"enabled", "items": [{id, app, type, label, text, html, course_id, course_name, url, created,
          read, read_at, seen}], "next_before", "links": {"feed", "settings"}}
    GET  /api/robbo/v1/notifications/service/unread-count/?user_id=
         {"enabled", "unread", "unseen"}
    POST /api/robbo/v1/notifications/service/read/   {"user_id", "ids": [..]} or {"user_id", "all": true}
         {"read": how many}
"""
from datetime import timedelta

from dateutil.parser import isoparse
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from rest_framework import status
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from openedx.core.djangoapps.notifications.models import Notification
from openedx.core.djangoapps.notifications.robbo_texts import (
    lang_of, notification_html, notification_text, type_label,
)
from openedx.core.djangoapps.notifications.utils import get_show_notifications_tray
from openedx.core.djangoapps.user_api.models import UserPreference
from openedx.core.lib.api.authentication import BearerAuthentication

from .api import mark_read

User = get_user_model()

DEFAULT_LIMIT = 30
MAX_LIMIT = 100


def service_users():
    return set(getattr(settings, 'ROBBO_NOTIFICATIONS_SERVICE_USERS', ()) or ())


class IsNotificationsService(BasePermission):
    """Only the configured service accounts (the LK server)."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active and user.username in service_users())


class _ServiceView(APIView):
    authentication_classes = (JwtAuthentication, BearerAuthentication)
    permission_classes = (IsNotificationsService,)

    @staticmethod
    def target_user(value):
        """The user whose notifications are asked for, or None."""
        try:
            user_id = int(value)
        except (TypeError, ValueError):
            return None
        return User.objects.filter(id=user_id, is_active=True).first()

    def not_found(self):
        return Response({'error': 'user_id: no such active user'}, status=status.HTTP_404_NOT_FOUND)


def notifications_enabled(user):
    """The LMS bell is shown to this user (notifications flag, courses: utils.get_show_notifications_tray)."""
    return bool(get_show_notifications_tray(user))


def visible_notifications(user):
    """The stock list: not expired, newest first (views.NotificationListAPIView)."""
    expiry = timezone.now() - timedelta(days=settings.NOTIFICATIONS_EXPIRY)
    return Notification.objects.filter(user=user, created__gte=expiry).order_by('-created', '-id')


def absolute_url(url):
    if url and url.startswith('/'):
        return f"{settings.LMS_ROOT_URL.rstrip('/')}{url}"
    return url or ''


def links():
    """Where LK sends the user for the full list and the settings (Account MFE on the LMS host)."""
    account = (getattr(settings, 'ACCOUNT_MICROFRONTEND_URL', None)
               or f"{settings.LMS_ROOT_URL.rstrip('/')}/account/").rstrip('/')
    return {'feed': f'{account}/notifications', 'settings': f'{account}/#notifications'}


def serialize(notification, lang):
    context = notification.content_context or {}
    html = notification_html(notification.notification_type, context, lang)
    text = notification_text(notification.notification_type, context, lang)
    return {
        'id': notification.id,
        'app': notification.app_name,
        'type': notification.notification_type,
        'label': type_label(notification.notification_type, lang),
        'text': text,
        'html': html,
        'course_id': str(notification.course_id) if notification.course_id else '',
        'course_name': context.get('course_name', ''),
        'url': absolute_url(notification.content_url),
        'created': notification.created.isoformat(),
        'read': notification.last_read is not None,
        'read_at': notification.last_read.isoformat() if notification.last_read else None,
        'seen': notification.last_seen is not None,
    }


class FeedView(_ServiceView):
    """The latest notifications of ``user_id``; ``before`` (an ISO time from next_before) pages back."""

    def get(self, request):
        user = self.target_user(request.query_params.get('user_id'))
        if user is None:
            return self.not_found()
        try:
            limit = min(max(int(request.query_params.get('limit', DEFAULT_LIMIT)), 1), MAX_LIMIT)
        except ValueError:
            limit = DEFAULT_LIMIT
        if not notifications_enabled(user):
            return Response({'enabled': False, 'items': [], 'next_before': None, 'links': links()})
        notifications = visible_notifications(user)
        before = request.query_params.get('before')
        if before:
            try:
                notifications = notifications.filter(created__lt=isoparse(before))
            except ValueError:
                return Response({'error': 'before: ISO 8601 time expected'}, status=status.HTTP_400_BAD_REQUEST)
        lang = lang_of(request.query_params.get('lang') or UserPreference.get_value(user, 'pref-lang')
                       or settings.LANGUAGE_CODE)
        page = list(notifications[:limit + 1])
        items = [serialize(notification, lang) for notification in page[:limit]]
        next_before = items[-1]['created'] if len(page) > limit else None
        return Response({'enabled': True, 'items': items, 'next_before': next_before, 'links': links()})


class UnreadCountView(_ServiceView):
    """How many notifications of ``user_id`` are unread (and not even seen)."""

    def get(self, request):
        user = self.target_user(request.query_params.get('user_id'))
        if user is None:
            return self.not_found()
        if not notifications_enabled(user):
            return Response({'enabled': False, 'unread': 0, 'unseen': 0})
        notifications = visible_notifications(user)
        return Response({
            'enabled': True,
            'unread': notifications.filter(last_read__isnull=True).count(),
            'unseen': notifications.filter(last_seen__isnull=True).count(),
        })


class ReadView(_ServiceView):
    """Marks notifications of ``user_id`` read: the listed ``ids`` or ``all``."""

    def post(self, request):
        user = self.target_user(request.data.get('user_id'))
        if user is None:
            return self.not_found()
        if request.data.get('all') is True:
            return Response({'read': mark_read(user)})
        ids = request.data.get('ids')
        if not isinstance(ids, list) or not ids or not all(isinstance(i, int) for i in ids):
            return Response({'error': 'ids: a non-empty list of integers, or all: true'},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({'read': mark_read(user, ids)})
