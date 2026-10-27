# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution. See NOTICE at repository root.
"""
Account MFE notification settings: the user's courses with what the course list sorts by, and
«Отключить все уведомления». The header bell: «Прочитать все».
"""
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.utils import timezone
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from edx_rest_framework_extensions.auth.session.authentication import SessionAuthenticationAllowInactiveUser
from opaque_keys import InvalidKeyError
from opaque_keys.edx.django.models import CourseKeyField
from opaque_keys.edx.keys import CourseKey
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.djangoapps.student.models import CourseAccessRole, CourseEnrollment
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from openedx.core.djangoapps.notifications import robbo_account, robbo_followers
from openedx.core.djangoapps.notifications.events import notifications_app_all_read_event
from openedx.core.djangoapps.notifications.models import CourseNotificationPreference, Notification
from openedx.core.djangoapps.notifications.serializers import add_info_to_notification_config
from openedx.core.djangoapps.notifications.utils import filter_out_visible_preferences_by_course_ids
from openedx.core.djangoapps.notifications.utils import ROBBO_COURSE_TEAM_ROLES


User = get_user_model()


class _UserView(APIView):
    authentication_classes = (JwtAuthentication, SessionAuthenticationAllowInactiveUser)
    permission_classes = (IsAuthenticated,)


class CoursesView(_UserView):
    """
    GET /api/robbo/v1/notifications/courses/ — the courses the user gets notifications for: active
    enrollments and courses where the user is in the course team (enrolled or not):
    [{id, name, start, created, enrolled, learners, team, details, customized}]; learners = active enrollments of
    the course, team = the user is staff / instructor / limited staff there. start, created and
    learners come with details = true: team courses, and every course for global staff / admins
    (null where the user is only a learner). Team courses get their
    notification preferences here, so account-wide settings reach them too.
    """

    def get(self, request):
        user = request.user
        site_staff = user.is_staff or user.is_superuser
        enrolled = {
            enrollment.course_id: enrollment
            for enrollment in CourseEnrollment.objects.filter(user=user, is_active=True)
        }
        team = set(CourseAccessRole.objects.filter(
            user=user, role__in=ROBBO_COURSE_TEAM_ROLES,
        ).exclude(course_id=CourseKeyField.Empty).values_list('course_id', flat=True))
        course_ids = set(enrolled) | team
        overviews = {overview.id: overview for overview in CourseOverview.objects.filter(id__in=course_ids)}
        for course_id in team - set(enrolled):
            CourseNotificationPreference.get_user_course_preference(user.id, course_id)
        customized = robbo_account.customized_course_ids(user)
        learners = dict(
            CourseEnrollment.objects.filter(course_id__in=course_ids, is_active=True)
            .values_list('course_id').annotate(total=Count('id'))
        )
        courses = []
        for course_id in course_ids:
            overview = overviews.get(course_id)
            if overview is None:
                continue
            enrollment = enrolled.get(course_id)
            in_team = course_id in team
            # Start, age and the number of learners: for the course team and for global staff / admins.
            details = in_team or site_staff
            courses.append({
                'id': str(course_id),
                'name': overview.display_name or str(course_id),
                'start': overview.start.isoformat() if details and overview.start else None,
                'created': overview.created.isoformat() if details and overview.created else None,
                'enrolled': enrollment.created.isoformat() if enrollment and enrollment.created else None,
                'learners': learners.get(course_id, 0) if details else None,
                'team': in_team,
                'details': details,
                # Differs from the stored settings «Для всех курсов» (robbo_account.py).
                'customized': course_id in customized,
            })
        return Response({'courses': courses})


class DisableAllView(_UserView):
    """
    POST /api/robbo/v1/notifications/disable-all/ — «Отключить все уведомления»: every type of every
    course of the user gets site, email and push off (channels the LMS marks non-editable stay as
    they are), and so do the stored settings «Для всех курсов» — courses joined later start off too.
    """

    def post(self, request):
        robbo_account.set_all_off(request.user)
        changed = 0
        for preference in CourseNotificationPreference.objects.filter(user=request.user, is_active=True):
            preference = CourseNotificationPreference.get_user_course_preference(request.user.id, preference.course_id)
            config = preference.notification_preference_config
            for app in config.values():
                locked = app.get('non_editable', {})
                for type_id, channels in app.get('notification_types', {}).items():
                    for channel in ('web', 'email', 'push'):
                        if channel not in locked.get(type_id, []) and channels.get(channel):
                            channels[channel] = False
                            changed += 1
            preference.notification_preference_config = config
            preference.save()
        return Response({'changed': changed})


def mark_read(user, ids=None):
    """Unread notifications of the user (all, or these ids) become read and seen. Returns how many."""
    now = timezone.now()
    unread = Notification.objects.filter(user=user, last_read__isnull=True)
    if ids is not None:
        unread = unread.filter(id__in=ids)
    apps = set(unread.values_list('app_name', flat=True))
    unread.filter(last_seen__isnull=True).update(last_seen=now)
    read = unread.update(last_read=now)
    if ids is None:
        for app_name in apps:
            notifications_app_all_read_event(user, app_name)
    return read


class ReadAllView(_UserView):
    """
    POST /api/robbo/v1/notifications/read-all/ — «Прочитать все» in the header bell: every unread
    notification of the user, of every app, becomes read (and seen) without opening the feed.
    {"read": how many}. The stock PATCH /api/notifications/read/ does it one app at a time.
    """

    def post(self, request):
        return Response({'read': mark_read(request.user)})


class AccountSettingsView(_UserView):
    """
    GET  /api/robbo/v1/notifications/account-settings/ — the stored settings «Для всех курсов» in the
         shape of the stock account view ({"data": config}), only the types the user can see.
    POST same, {notification_app, notification_type, notification_channel, value} — changes one
         channel (web, email, email_cadence) there and in the courses that still follow it.
    """

    def get(self, request):
        user = request.user
        config = robbo_account.account_config(user)
        course_ids = list(
            CourseNotificationPreference.objects.filter(user=user, is_active=True).values_list('course_id', flat=True)
        )
        filter_out_visible_preferences_by_course_ids(user, config, course_ids)
        return Response({'status': 'success', 'data': add_info_to_notification_config(config)})

    def post(self, request):
        data = request.data
        try:
            updated = robbo_account.set_account_value(
                request.user, data.get('notification_app'), data.get('notification_type'),
                data.get('notification_channel'), data.get('value'),
            )
        except ValueError as error:
            return Response({'error': str(error)}, status=400)
        return Response({'status': 'success', 'updated_courses': updated})


class ResetCoursesView(_UserView):
    """
    POST /api/robbo/v1/notifications/courses/reset/ {course_ids: [...]} — the stored settings
    «Для всех курсов» back into these courses («Вернуть общие настройки»). {reset: number changed}
    """

    def post(self, request):
        course_ids = request.data.get('course_ids') or []
        return Response({'reset': robbo_account.reset_courses(request.user, course_ids)})


class CourseLearnersView(_UserView):
    """
    Which learners a course-team member gets notifications about (robbo_followers.py).

    GET  /api/robbo/v1/notifications/learners/?course_id=…&q=…&limit=… —
         {mode: "all"|"selected", selected: [learner], learners: [learner + followed], total}
         learner = {id, username, name}; learners are active enrollments outside the course team,
         filtered by q (username or name).
    POST same URL, {course_id, mode: "all"} or {course_id, mode: "selected", learner_ids: [...]}.
    Course team only (staff, instructor, limited staff): 403 for learners.
    """

    def _course(self, request, course_id):
        try:
            course_key = CourseKey.from_string(course_id or '')
        except InvalidKeyError:
            return None, Response({'error': 'course_id'}, status=400)
        is_team = CourseAccessRole.objects.filter(
            user=request.user, course_id=course_key, role__in=ROBBO_COURSE_TEAM_ROLES,
        ).exists()
        if not is_team:
            return None, Response({'error': 'course team only'}, status=403)
        return course_key, None

    @staticmethod
    def _learners(course_key):
        team = CourseAccessRole.objects.filter(course_id=course_key).values_list('user_id', flat=True)
        return (
            User.objects.filter(courseenrollment__course_id=course_key, courseenrollment__is_active=True)
            .exclude(id__in=team).select_related('profile').distinct()
        )

    @staticmethod
    def _row(user, followed=None):
        row = {'id': user.id, 'username': user.username, 'name': getattr(getattr(user, 'profile', None), 'name', '')}
        if followed is not None:
            row['followed'] = followed
        return row

    def _state(self, user, course_key, query='', limit=50):
        chosen = robbo_followers.selection(user, course_key)
        learners = self._learners(course_key)
        if query:
            learners = learners.filter(Q(username__icontains=query) | Q(profile__name__icontains=query))
        chosen_set = set(chosen or [])
        page = list(learners.order_by('profile__name', 'username')[:limit])
        selected = list(User.objects.filter(id__in=chosen_set).select_related('profile')) if chosen else []
        return Response({
            'mode': 'all' if chosen is None else 'selected',
            'selected': [self._row(learner) for learner in selected],
            'learners': [self._row(learner, chosen is None or learner.id in chosen_set) for learner in page],
            'total': learners.count(),
        })

    def get(self, request):
        course_key, error = self._course(request, request.query_params.get('course_id'))
        if error:
            return error
        try:
            limit = max(1, min(int(request.query_params.get('limit', 50)), 200))
        except ValueError:
            limit = 50
        return self._state(request.user, course_key, (request.query_params.get('q') or '').strip(), limit)

    def post(self, request):
        course_key, error = self._course(request, request.data.get('course_id'))
        if error:
            return error
        if request.data.get('mode') == 'all':
            robbo_followers.set_selection(request.user, course_key, None)
        else:
            wanted = {int(i) for i in request.data.get('learner_ids') or [] if str(i).isdigit()}
            allowed = set(self._learners(course_key).filter(id__in=wanted).values_list('id', flat=True))
            robbo_followers.set_selection(request.user, course_key, sorted(allowed))
        return self._state(request.user, course_key)
