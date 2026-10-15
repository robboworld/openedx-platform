# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (course groups). See NOTICE at repository root.

"""
Invite links of course groups: issue, replace, switch on and off; join a group by its link.
Members of a group for the «Группы» tab: list and search them, take one out of the group or the course;
delete a group.
"""

import logging

from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import EmptyPage, Paginator
from django.db import transaction
from django.db.models import Q

from common.djangoapps.course_modes.models import CourseMode
from common.djangoapps.student.models import CourseEnrollment, EnrollmentNotAllowed
from openedx.core.djangoapps.course_groups.cohorts import (
    add_user_to_cohort,
    get_cohort,
    is_last_random_cohort,
    remove_user_from_cohort,
)
from openedx.core.djangoapps.course_groups.models import (
    CohortMembership,
    CohortMembershipException,
    CourseCohort,
    CourseUserGroup,
)

from .models import GroupInvite, generate_invite_code

log = logging.getLogger(__name__)
User = get_user_model()

MEMBERS_PAGE_SIZE = 20


class JoinNotAllowed(Exception):
    """The learner can't join the group by this link; the page shows a generic message."""


class NotAMember(Exception):
    """The learner is not in the group (any more): someone else moved or removed them meanwhile."""


class AutomaticGroup(Exception):
    """Nobody leaves an automatic group by «Убрать из группы»: Open edX would put them into one again."""


class DefaultGroup(Exception):
    """
    The only automatic group of the course is not deleted: everyone not placed elsewhere goes there, and
    without it Open edX would create a new «Default Group» at once (its type can't be changed either).
    """


def get_invite(cohort):
    return GroupInvite.objects.filter(cohort=cohort).first()


def issue_invite(cohort, user):
    """A new code for the group's link; the previous link, if any, stops working."""
    invite = get_invite(cohort)
    if invite is None:
        invite = GroupInvite.objects.create(cohort=cohort, created_by=user)
    else:
        invite.code = generate_invite_code()
        invite.is_active = True
        invite.created_by = user
        invite.save()
    log.info('robbo_groups: %s issued an invite for cohort %s in %s', user.username, cohort.id, cohort.course_id)
    return invite


def set_invite_active(invite, is_active, user):
    invite.is_active = is_active
    invite.save(update_fields=['is_active', 'modified'])
    log.info(
        'robbo_groups: %s %s the invite of cohort %s in %s',
        user.username, 'enabled' if is_active else 'disabled', invite.cohort_id, invite.cohort.course_id,
    )


def find_active_invite(code):
    return GroupInvite.objects.select_related('cohort').filter(
        code=(code or '').strip().lower(),
        is_active=True,
        cohort__group_type=CourseUserGroup.COHORT,
    ).first()


def is_automatic(cohort):
    return CourseCohort.objects.filter(course_user_group=cohort, assignment_type=CourseCohort.RANDOM).exists()


def placed_cohort(user, course_key):
    """
    The group of the course the learner was placed in on purpose, or None: a manual one (the teacher added
    them) or one with an invite link (they joined by it). An automatic group does not count: Open edX puts
    every learner of a cohorted course into one on the first visit, and an invite link still moves them.
    """
    membership = CohortMembership.objects.select_related('course_user_group').filter(
        user=user, course_id=course_key,
    ).first()
    if membership is None:
        return None
    cohort = membership.course_user_group
    if is_automatic(cohort) and not GroupInvite.objects.filter(cohort=cohort).exists():
        return None
    return cohort


def is_settled(user, invite):
    """
    The link has nothing to do for the learner: enrolled and placed in a group of the course, this one or
    another (a link doesn't move a placed learner, see join_by_invite). The page sends them to the course.
    """
    course_key = invite.cohort.course_id
    return CourseEnrollment.is_enrolled(user, course_key) and placed_cohort(user, course_key) is not None


def join_by_invite(user, invite):
    """
    Enroll the learner (if needed) and put them into the invite's group.

    A new enrollment gets the free mode («honor», else «audit»), whatever the course enrollment
    window, invitation-only flag or catalog visibility say: the teacher invited this learner.
    An existing enrollment keeps its mode, so a paid one stays paid.

    A learner already placed in another group of the course (placed_cohort) stays there: an old or
    forwarded link must not undo the teacher's choice. Only the teacher moves them, in «Группы».
    """
    cohort = invite.cohort
    course_key = cohort.course_id
    with transaction.atomic():
        enrollment = CourseEnrollment.get_enrollment(user, course_key)
        if enrollment is None or not enrollment.is_active:
            mode = enrollment.mode if enrollment else CourseMode.auto_enroll_mode(course_key)
            if not mode:
                raise JoinNotAllowed(f'{course_key} has no free course mode')
            try:
                CourseEnrollment.enroll(user, course_key, mode=mode, check_access=False)
            except EnrollmentNotAllowed as exc:
                raise JoinNotAllowed(str(exc)) from exc
        placed = placed_cohort(user, course_key)
        if placed is not None:
            if placed != cohort:
                log.info(
                    'robbo_groups: user %s stays in cohort %s in %s, not moved by the invite of cohort %s',
                    user.id, placed.id, course_key, cohort.id,
                )
            return
        try:
            add_user_to_cohort(cohort, user)
        except ValueError:
            pass  # already in this group (a second click)
        except CohortMembershipException as exc:
            raise JoinNotAllowed(str(exc)) from exc
    log.info('robbo_groups: user %s joined cohort %s in %s by invite', user.id, cohort.id, course_key)


def _display_name(user):
    try:
        name = user.profile.name
    except ObjectDoesNotExist:
        name = ''
    return (name or f'{user.first_name} {user.last_name}').strip()


def cohort_members(cohort, query='', page=1):
    """
    One page of the group's members, by name, then username; `query` matches the name, username or email.

    Returns ``(members, count, has_more)``; a member is ``{username, email, name, is_enrolled, is_paid}``.
    Unlike the group's count in the cohort list, learners who left the course are here too
    (``is_enrolled`` is False): they are still in the group and come back to it if enrolled again.
    """
    users = cohort.users.select_related('profile').order_by('profile__name', 'username')
    query = (query or '').strip()
    if query:
        users = users.filter(
            Q(profile__name__icontains=query)
            | Q(username__icontains=query)
            | Q(email__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
        )
    paginator = Paginator(users, MEMBERS_PAGE_SIZE)
    try:
        page_users = list(paginator.page(page))
    except EmptyPage:
        return [], paginator.count, False
    modes = dict(
        CourseEnrollment.objects.filter(
            course_id=cohort.course_id, user__in=page_users, is_active=True,
        ).values_list('user_id', 'mode')
    )
    members = [
        {
            'username': user.username,
            'email': user.email,
            'name': _display_name(user),
            'is_enrolled': user.id in modes,
            # paid through robbo_payments (YooKassa): the confirmation of «Удалить с курса» says so
            'is_paid': modes.get(user.id) in CourseMode.VERIFIED_MODES,
        }
        for user in page_users
    ]
    return members, paginator.count, page < paginator.num_pages


def _member(cohort, username):
    membership = CohortMembership.objects.select_related('user').filter(
        course_user_group=cohort, user__username=username,
    ).first()
    if membership is None:
        raise NotAMember(username)
    return membership.user


def _leave_group(cohort, user):
    """
    Delete the membership; NotAMember if it is gone already (someone else was quicker).

    For an enrolled learner the regular way, with COHORT_MEMBERSHIP_UPDATED: their grades are recalculated,
    since what they see changed. Not for a learner who is not enrolled: the recalculation task builds the
    course for them, and get_cohort there would put them right back into an automatic group — while they
    have no grades to recalculate.
    """
    if CourseEnrollment.is_enrolled(user, cohort.course_id):
        try:
            remove_user_from_cohort(cohort, user.username)
        except ValueError as exc:
            raise NotAMember(user.username) from exc
        return
    deleted, _ = CohortMembership.objects.filter(course_user_group=cohort, user=user).delete()
    if not deleted:
        raise NotAMember(user.username)


def _place_in_automatic_group(user, course_key):
    """Open edX's own assignment (an automatic group, «Default Group» if none), for an enrolled learner."""
    if not CourseEnrollment.is_enrolled(user, course_key):
        return None
    return get_cohort(user, course_key, assign=True)


def remove_member(cohort, username, removed_by):
    """
    Take the learner out of the group («Убрать из группы»). They stay enrolled and go to an automatic group
    right away (the «Default Group», created if the course has none), as Open edX would do on their next
    visit anyway: the counts of both groups change at once. An invite link can place them again
    (placed_cohort). Someone who left the course is not placed until they come back.

    Returns the automatic group, or None. Raises AutomaticGroup for an automatic group,
    NotAMember if the learner is not in this group (any more).
    """
    if is_automatic(cohort):
        raise AutomaticGroup(cohort.name)
    user = _member(cohort, username)
    _leave_group(cohort, user)
    new_cohort = _place_in_automatic_group(user, cohort.course_id)
    log.info(
        'robbo_groups: %s removed user %s from cohort %s in %s, now in cohort %s',
        removed_by.username, user.id, cohort.id, cohort.course_id, new_cohort and new_cohort.id,
    )
    return new_cohort


def unenroll_member(cohort, username, unenrolled_by):
    """
    «Удалить с курса»: unenroll the learner and take them out of the group, so a later invite link places
    them anew. Their progress stays: enrolled again, they go on where they stopped. A paid enrollment is not
    refunded (robbo_payments has no refunds; skip_refund keeps Open edX from trying one).
    Raises NotAMember if they are not in this group (any more).
    """
    user = _member(cohort, username)
    with transaction.atomic():
        CourseEnrollment.unenroll(user, cohort.course_id, skip_refund=True)
        _leave_group(cohort, user)  # not enrolled any more: stays out of any group
    log.info(
        'robbo_groups: %s unenrolled user %s from %s, out of cohort %s',
        unenrolled_by.username, user.id, cohort.course_id, cohort.id,
    )


def delete_group(cohort, deleted_by):
    """
    «Удалить группу»: the group goes together with its invite link, its link to a content group and its
    pre-assigned emails. Its learners stay in the course and go to an automatic group right away, as with
    remove_member. Returns the names of the groups they went to. Raises DefaultGroup for the only automatic
    group of the course.
    """
    if is_last_random_cohort(cohort):
        raise DefaultGroup(cohort.name)
    course_key = cohort.course_id
    cohort_id = cohort.id
    users = list(User.objects.filter(cohortmembership__course_user_group=cohort))
    with transaction.atomic():
        cohort.delete()
    new_groups = set()
    for user in users:
        new_cohort = _place_in_automatic_group(user, course_key)
        if new_cohort is not None:
            new_groups.add(new_cohort.name)
    log.info(
        'robbo_groups: %s deleted cohort %s in %s, %s learners moved to %s',
        deleted_by.username, cohort_id, course_key, len(users), sorted(new_groups),
    )
    return sorted(new_groups)
