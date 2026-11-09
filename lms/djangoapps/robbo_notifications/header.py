# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution. See NOTICE at repository root.
"""
First state of the header bell on LMS and Studio Mako pages.

The header renders it into ``data-initial`` — the fields of ``/api/notifications/count/`` the widget
reads — so the bell shows together with the page instead of after a request. MFEs keep the request.
"""

import json
import logging

from django.db.models import Count

from openedx.core.djangoapps.notifications.models import Notification
from openedx.core.djangoapps.notifications.utils import get_show_notifications_tray

log = logging.getLogger(__name__)


def initial_state(user):
    """``show_notifications_tray``, ``count`` and ``count_by_app_name`` as NotificationCountView counts them."""
    by_app = dict(
        Notification.objects
        .filter(user_id=user, last_seen__isnull=True, web=True)
        .values_list('app_name')
        .annotate(count=Count('*'))
    )
    return {
        'show_notifications_tray': get_show_notifications_tray(user),
        'count': sum(by_app.values()),
        'count_by_app_name': by_app,
    }


def initial_json(user):
    """``initial_state`` as JSON; empty for guests, accounts not activated yet and on any error (the widget asks the API)."""
    if not (user.is_authenticated and user.is_active):
        return ''
    try:
        return json.dumps(initial_state(user))
    except Exception:  # pylint: disable=broad-except
        log.exception('robbo_notifications: header state for %s failed', user.id)
        return ''
