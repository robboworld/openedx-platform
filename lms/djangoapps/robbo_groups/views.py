# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (course groups). See NOTICE at repository root.

"""
/join/<code>: the page a learner opens from a group invite link.
courses/<id>/cohorts/<cohort_id>/robbo-invite: the link of one group for the instructor dashboard «Группы» tab.
courses/<id>/cohorts/<cohort_id>/robbo-members: the members of one group there, with «Убрать из группы» and
«Удалить с курса»; .../robbo-delete: «Удалить группу».
"""

import logging
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey

from common.djangoapps.edxmako.shortcuts import render_to_response
from lms.djangoapps.courseware.access import has_access
from lms.djangoapps.courseware.robbo_catalog import _catalog_course_image_url, _catalog_course_uses_placeholder_image
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from openedx.core.djangoapps.course_groups.models import CourseUserGroup
from openedx.features.course_experience.url_helpers import get_learning_mfe_home_url

from . import api

log = logging.getLogger(__name__)

# Set by the «Войти» / «Зарегистрироваться» buttons of the join page (a CSRF-protected POST), so the
# learner who comes back from sign-in or sign-up joins the group without one more click.
JOIN_INTENT_SESSION_KEY = 'robbo_groups_join_code'


def _render_join(state, status=200, **context):
    return render_to_response('robbo_groups/join.html', {'state': state, **context}, status=status)


# A whole class behind one school IP opens the link at once (3–4 requests each), and guessing a code
# (31^10 of them) is hopeless anyway: the limit only stops a runaway scanner.
@ratelimit(key='openedx.core.djangoapps.util.ratelimit.real_ip', rate='600/m', method=['GET', 'POST'], block=True)
@ensure_csrf_cookie
@require_http_methods(['GET', 'POST'])
def join(request, code):
    invite = api.find_active_invite(code)
    try:
        course = CourseOverview.get_from_id(invite.cohort.course_id) if invite else None
    except CourseOverview.DoesNotExist:
        course = None
    if course is None:
        return _render_join('invalid', status=404)

    cohort = invite.cohort
    # No group name: the learner sees the course; how the teacher named the group is not their business.
    context = {
        'course_name': course.display_name_with_default,
        'course_description': course.short_description,
        'course_image_url': (
            None if _catalog_course_uses_placeholder_image(course) else _catalog_course_image_url(course)
        ),
    }
    join_path = reverse('robbo_groups:join', args=[invite.code])
    user = request.user

    if not user.is_authenticated:
        if request.method == 'POST':
            request.session[JOIN_INTENT_SESSION_KEY] = invite.code
            auth_url = reverse('signin_user' if request.POST.get('then') == 'login' else 'register_user')
            return redirect(f'{auth_url}?{urlencode({"next": join_path})}')
        return _render_join('anonymous', join_url=join_path, **context)

    course_home_url = get_learning_mfe_home_url(course_key=cohort.course_id, url_fragment='home')
    if request.method == 'POST' or request.session.get(JOIN_INTENT_SESSION_KEY) == invite.code:
        request.session.pop(JOIN_INTENT_SESSION_KEY, None)
        try:
            api.join_by_invite(user, invite)
        except api.JoinNotAllowed as exc:
            log.warning('robbo_groups: user %s could not join cohort %s: %s', user.id, cohort.id, exc)
            return _render_join('unavailable', status=403, **context)
        return redirect(course_home_url)

    if api.is_settled(user, invite):
        return redirect(course_home_url)

    return _render_join(
        'confirm',
        join_url=join_path,
        username=user.username,
        logout_url=f'{reverse("logout")}?{urlencode({"redirect_url": join_path})}',
        **context,
    )


def _invite_json(request, invite):
    if invite is None:
        return {'url': None, 'is_active': False}
    return {
        'url': request.build_absolute_uri(reverse('robbo_groups:join', args=[invite.code])),
        'is_active': invite.is_active,
    }


def _course_team_cohort(request, course_id, cohort_id):
    """The group, or None if the user is not on the course team. 404 for an unknown course or group."""
    try:
        course_key = CourseKey.from_string(course_id)
    except InvalidKeyError as exc:
        raise Http404 from exc
    if not has_access(request.user, 'staff', course_key):
        return None
    return get_object_or_404(
        CourseUserGroup, id=cohort_id, course_id=course_key, group_type=CourseUserGroup.COHORT,
    )


@login_required
@require_http_methods(['GET', 'POST'])
def cohort_invite(request, course_id, cohort_id):
    """
    GET: the group's link. POST action=issue — a new link (the old one stops working),
    action=enable / disable — switch the current link on or off. Course team only.
    """
    cohort = _course_team_cohort(request, course_id, cohort_id)
    if cohort is None:
        return JsonResponse({'error': 'forbidden'}, status=403)
    invite = api.get_invite(cohort)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'issue':
            invite = api.issue_invite(cohort, request.user)
        elif action in ('enable', 'disable') and invite is not None:
            api.set_invite_active(invite, action == 'enable', request.user)
        else:
            return JsonResponse({'error': 'unknown action'}, status=400)

    return JsonResponse(_invite_json(request, invite))


@login_required
@require_http_methods(['GET', 'POST'])
def cohort_members(request, course_id, cohort_id):
    """
    GET ?q=&page=: one page of the group's members (api.cohort_members).
    POST username=: take the learner out of the group (api.remove_member), answers with the automatic group
    they went to; 400 for an automatic group. POST action=unenroll, username=: «Удалить с курса»
    (api.unenroll_member). 409 if the learner is not in the group any more. Course team only.
    """
    cohort = _course_team_cohort(request, course_id, cohort_id)
    if cohort is None:
        return JsonResponse({'error': 'forbidden'}, status=403)

    if request.method == 'POST':
        username = request.POST.get('username', '')
        action = request.POST.get('action', 'remove')
        try:
            if action == 'unenroll':
                api.unenroll_member(cohort, username, request.user)
                return JsonResponse({'unenrolled': username})
            if action != 'remove':
                return JsonResponse({'error': 'unknown action'}, status=400)
            new_cohort = api.remove_member(cohort, username, request.user)
        except api.AutomaticGroup:
            return JsonResponse({'error': 'automatic group'}, status=400)
        except api.NotAMember:
            return JsonResponse({'error': 'not a member'}, status=409)
        return JsonResponse({'removed': username, 'new_group': new_cohort.name if new_cohort else None})

    try:
        page = max(int(request.GET.get('page', 1)), 1)
    except ValueError:
        page = 1
    members, count, has_more = api.cohort_members(cohort, request.GET.get('q', ''), page)
    return JsonResponse({'members': members, 'count': count, 'page': page, 'has_more': has_more})


@login_required
@require_http_methods(['POST'])
def cohort_delete(request, course_id, cohort_id):
    """
    «Удалить группу» (api.delete_group); answers with the groups its learners went to,
    400 for the default group. Course team only.
    """
    cohort = _course_team_cohort(request, course_id, cohort_id)
    if cohort is None:
        return JsonResponse({'error': 'forbidden'}, status=403)
    name = cohort.name
    try:
        new_groups = api.delete_group(cohort, request.user)
    except api.DefaultGroup:
        return JsonResponse({'error': 'default group'}, status=400)
    return JsonResponse({'deleted': name, 'new_groups': new_groups})
