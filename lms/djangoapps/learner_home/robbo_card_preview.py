# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of the Robbo Open edX distribution. See NOTICE at repository root.

"""
Course card preview in «Мои курсы»: ``/api/learner_home/init?robbo_card_preview=<course key>``
adds ``robboCardPreview`` with the card a learner gets right after enrolling.

The card goes through the regular ``LearnerEnrollmentSerializer`` with an unsaved enrollment
and a learner context (nothing started, no certificate, no staff access), so the MFE renders it
with the real ``CourseCard``. Access rules and links: ``courseware.robbo_card_preview``.

``CourseCardPreviewView`` gives Studio (card image field) the same catalog and dashboard card
data, so its mock-ups can show what the form does not have (unit count, passing grade, mode).
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from django.conf import settings
from django.http import Http404
from django.utils import timezone
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from edx_rest_framework_extensions.auth.session.authentication import (
    SessionAuthenticationAllowInactiveUser,
)
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.djangoapps.course_modes.models import CourseMode
from common.djangoapps.student.models import CourseEnrollment
from lms.djangoapps.courseware.robbo_card_preview import (
    CARD_PREVIEW_CATALOG,
    get_card_preview_course_key,
    get_card_preview_overview,
    get_card_preview_studio_url,
    get_card_preview_url,
    user_can_preview_course_card,
)
from lms.djangoapps.learner_home.serializers import LearnerEnrollmentSerializer
from openedx.features.course_experience import COURSE_PRE_START_ACCESS_FLAG


def _is_too_early_for_learner(overview) -> bool:
    """``check_course_open_for_learner`` for a learner without staff or beta access."""
    if settings.FEATURES.get('DISABLE_START_DATES') or COURSE_PRE_START_ACCESS_FLAG.is_enabled():
        return False
    return overview.start is not None and timezone.now() < overview.start


def _new_learner_progress(user, overview) -> Dict[Any, Dict[str, int]]:
    """Zero progress over the course units (counted for the author: staff-only units included)."""
    from lms.djangoapps.courseware.robbo_course_progress import get_courses_progress  # pylint: disable=import-outside-toplevel

    progress = get_courses_progress(user, [overview]).get(overview.id)
    if not progress:
        return {}
    return {overview.id: {'completed': 0, 'total': progress['total'], 'percent': 0}}


def _serialize_preview_card(user, overview) -> Dict[str, Any]:
    course_key = overview.id
    enrollment = CourseEnrollment(
        user=user,
        course_id=course_key,
        mode=CourseMode.auto_enroll_mode(course_key) or CourseMode.DEFAULT_MODE_SLUG,
        is_active=True,
    )
    enrollment.course = overview
    context = {
        'audit_access_deadlines': {},
        'ecommerce_payment_page': None,
        'cert_statuses': {},
        'course_mode_info': {},
        'course_optouts': [],
        'course_access_checks': {
            course_key: {
                'has_unmet_prerequisites': False,
                'is_too_early_to_view': _is_too_early_for_learner(overview),
                'user_has_staff_access': False,
            },
        },
        'credit_statuses': {},
        'grade_statuses': {},
        'resume_course_urls': {},
        'resume_block_titles': {},
        'course_progress': _new_learner_progress(user, overview),
        'course_share_urls': {},
        'show_email_settings_for': [],
        'fulfilled_entitlements': {},
        'programs': {},
    }
    return LearnerEnrollmentSerializer(enrollment, context=context).data


def get_learner_home_card_preview(request, user) -> Optional[Dict[str, Any]]:
    """``robboCardPreview`` for the init response, or None without an allowed preview request."""
    course_key = get_card_preview_course_key(request)
    if course_key is None:
        return None
    overview = get_card_preview_overview(course_key)
    if overview is None:
        return None
    return {
        'courseId': str(course_key),
        'courseName': overview.display_name_with_default,
        'catalogPreviewUrl': get_card_preview_url(course_key, CARD_PREVIEW_CATALOG),
        'studioUrl': get_card_preview_studio_url(course_key),
        'card': _serialize_preview_card(user, overview),
    }


class CourseCardPreviewView(APIView):
    """
    GET ``/api/robbo/v1/course-card-preview/<course key>/``: the catalog card (as for a learner
    who is not enrolled) and the «Мои курсы» card (right after enrolling) of the saved course.
    """

    authentication_classes = (JwtAuthentication, SessionAuthenticationAllowInactiveUser)
    permission_classes = (IsAuthenticated,)

    def get(self, request, course_id):
        """Same access as the preview pages: whoever may edit the course in Studio."""
        from lms.djangoapps.courseware.robbo_catalog import build_robbo_catalog_course_cards  # pylint: disable=import-outside-toplevel

        try:
            course_key = CourseKey.from_string(course_id)
        except InvalidKeyError as exc:
            raise Http404 from exc
        if not user_can_preview_course_card(request.user, course_key):
            raise PermissionDenied
        overview = get_card_preview_overview(course_key)
        if overview is None:
            raise Http404

        catalog = build_robbo_catalog_course_cards(request, [overview], as_new_learner=True)[0]
        catalog['advertised_start'] = overview.advertised_start or None
        return Response({
            'catalog': catalog,
            'dashboard': _serialize_preview_card(request.user, overview),
        })
