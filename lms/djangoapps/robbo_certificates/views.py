# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (certificate designs). See NOTICE at repository root.
"""
One-click fixes from the instructor dashboard «Сертификаты» tab (platform staff / superusers only):
add the «honor» course mode, remove «audit» next to «honor»,
move active «audit» enrollments to «honor» (paid «verified» ones stay),
allow self-generated certificates for the course,
repair a malformed certificates display behavior.
"""

import logging

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, HttpResponseForbidden, HttpResponseRedirect
from django.urls import reverse
from django.views.decorators.http import require_POST
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey

from common.djangoapps.course_modes.models import CourseMode
from xmodule.modulestore import ModuleStoreEnum
from xmodule.modulestore.django import modulestore
from common.djangoapps.student.models import CourseEnrollment
from lms.djangoapps.certificates import api as certs_api
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview

from .readiness import can_fix_course, display_behavior_repair_value

log = logging.getLogger(__name__)


def _course_key_or_404(course_id):
    try:
        course_key = CourseKey.from_string(course_id)
    except InvalidKeyError as exc:
        raise Http404 from exc
    if not CourseOverview.course_exists(course_key):
        raise Http404
    return course_key


def _back_to_tab(course_key):
    return HttpResponseRedirect(
        reverse('instructor_dashboard', kwargs={'course_id': str(course_key)}) + '#view-certificates'
    )


@login_required
@require_POST
def add_honor_mode(request, course_id):
    course_key = _course_key_or_404(course_id)
    if not can_fix_course(request.user):
        return HttpResponseForbidden()
    _, created = CourseMode.objects.get_or_create(
        course_id=course_key, mode_slug=CourseMode.HONOR,
        defaults={'mode_display_name': 'Honor', 'min_price': 0},
    )
    if created:
        log.info('robbo_certificates: %s added honor mode to %s', request.user.username, course_key)
    return _back_to_tab(course_key)


@login_required
@require_POST
def remove_audit_mode(request, course_id):
    """Only next to «honor»: a course with «audit» alone (or «audit» + «verified») is left as is."""
    course_key = _course_key_or_404(course_id)
    if not can_fix_course(request.user):
        return HttpResponseForbidden()
    modes = CourseMode.objects.filter(course_id=course_key)
    if modes.filter(mode_slug=CourseMode.HONOR).exists():
        deleted, _ = modes.filter(mode_slug=CourseMode.AUDIT).delete()
        if deleted:
            log.info('robbo_certificates: %s removed audit mode from %s', request.user.username, course_key)
    return _back_to_tab(course_key)


@login_required
@require_POST
def enrollments_to_honor(request, course_id):
    course_key = _course_key_or_404(course_id)
    if not can_fix_course(request.user):
        return HttpResponseForbidden()
    if not CourseMode.objects.filter(course_id=course_key, mode_slug=CourseMode.HONOR).exists():
        # Without the mode, enrollments in it would not be selectable or eligible
        return _back_to_tab(course_key)

    enrollments = (
        CourseEnrollment.objects.filter(course_id=course_key, is_active=True, mode=CourseMode.AUDIT)
        .select_related('user')
    )
    moved = 0
    with transaction.atomic():
        for enrollment in enrollments:
            # update_enrollment emits the mode-change events/signals like a manual change would
            enrollment.update_enrollment(mode=CourseMode.HONOR)
            moved += 1
    log.info(
        'robbo_certificates: %s moved %d audit enrollments of %s to honor', request.user.username, moved, course_key,
    )
    return _back_to_tab(course_key)


@login_required
@require_POST
def enable_self_generation(request, course_id):
    """Course setting behind «Разрешить обучающимся выпускать себе сертификаты» (also for self-paced courses)."""
    course_key = _course_key_or_404(course_id)
    if not can_fix_course(request.user):
        return HttpResponseForbidden()
    certs_api.set_cert_generation_enabled(course_key, True)
    log.info(
        'robbo_certificates: %s enabled self-generated certificates for %s', request.user.username, course_key,
    )
    return _back_to_tab(course_key)


@login_required
@require_POST
def repair_display_behavior(request, course_id):
    """
    Rewrite a malformed certificates_display_behavior ('CertificatesDisplayBehaviors.X' or unknown).
    The course block is auto-published, so CourseOverview is refreshed by the course_published signal.
    """
    course_key = _course_key_or_404(course_id)
    if not can_fix_course(request.user):
        return HttpResponseForbidden()
    store = modulestore()
    with store.branch_setting(ModuleStoreEnum.Branch.draft_preferred, course_key), store.bulk_operations(course_key):
        course = store.get_course(course_key)
        repaired = display_behavior_repair_value(course.certificates_display_behavior)
        if repaired is not None:
            log.info(
                'robbo_certificates: %s repaired certificates_display_behavior of %s: %r -> %r',
                request.user.username, course_key, course.certificates_display_behavior, repaired,
            )
            course.certificates_display_behavior = repaired
            store.update_item(course, request.user.id)
    return _back_to_tab(course_key)
