# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (certificate designs). See NOTICE at repository root.
"""
Whether a course issues certificates, and turning it on (Studio «Тип курса»).

A free course issues certificates when learners enroll in «honor»: «audit» never gets one (see
readiness.py). Turning certificates on does at once what the one-click fixes of the instructor
dashboard «Сертификаты» tab do one by one (views.py): add «honor», remove «audit» so new learners
enroll in «honor», move the active «audit» enrollments to «honor». Paid «verified» enrollments are
not touched.
"""

import logging

from django.db import transaction

from common.djangoapps.course_modes.models import CourseMode
from common.djangoapps.student.models import CourseEnrollment

log = logging.getLogger(__name__)


def issues_certificates(course_key):
    """The course has the «honor» mode."""
    return CourseMode.objects.filter(course_id=course_key, mode_slug=CourseMode.HONOR).exists()


def audit_learners(course_key):
    return CourseEnrollment.objects.filter(course_id=course_key, is_active=True, mode=CourseMode.AUDIT).count()


@transaction.atomic
def enable_certificates(course_key, user=None):
    """
    Make the course issue certificates; idempotent. Returns
    ``{'added_honor': bool, 'removed_audit': bool, 'moved': int}``.
    """
    _mode, added = CourseMode.objects.get_or_create(
        course_id=course_key, mode_slug=CourseMode.HONOR,
        defaults={'mode_display_name': 'Honor', 'min_price': 0},
    )
    removed, _ = CourseMode.objects.filter(course_id=course_key, mode_slug=CourseMode.AUDIT).delete()
    moved = 0
    enrollments = CourseEnrollment.objects.filter(
        course_id=course_key, is_active=True, mode=CourseMode.AUDIT,
    ).select_related('user')
    for enrollment in enrollments:
        # update_enrollment emits the mode-change events/signals like a manual change would
        enrollment.update_enrollment(mode=CourseMode.HONOR)
        moved += 1
    log.info(
        'robbo_certificates: %s turned certificates on for %s (honor added: %s, audit removed: %s, moved: %d)',
        getattr(user, 'username', None), course_key, added, bool(removed), moved,
    )
    return {'added_honor': added, 'removed_audit': bool(removed), 'moved': moved}
