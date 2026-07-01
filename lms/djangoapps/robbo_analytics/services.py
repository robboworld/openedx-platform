# Copyright (C) 2024-2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of the Robbo Open edX distribution. See NOTICE at repository root.

"""
Data helpers for Robbo global analytics.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional

from django.db.models import Avg, Max
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.formats import date_format
from django.utils.timezone import localtime
from django.utils.translation import ngettext

from common.djangoapps.student.models import CourseEnrollment
from lms.djangoapps.courseware.models import StudentModule
from lms.djangoapps.grades.models import PersistentCourseGrade
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview

log = logging.getLogger(__name__)

COURSE_FILTER_ACTIVE = 'active'
COURSE_FILTER_ALL = 'all'
COURSE_FILTER_ARCHIVED = 'archived'
COURSE_FILTERS = frozenset({
    COURSE_FILTER_ACTIVE,
    COURSE_FILTER_ALL,
    COURSE_FILTER_ARCHIVED,
})

DROPOUT_INACTIVITY_DAYS = 30
EMPTY_DISPLAY = '—'


def _display(value: Any) -> str:
    if value is None or value == '':
        return EMPTY_DISPLAY
    return force_str(value)


def _format_grade(value: Optional[float]) -> str:
    if value is None:
        return EMPTY_DISPLAY
    return f'{float(value):.1f}%'


def _format_date(value) -> str:
    if not value:
        return EMPTY_DISPLAY
    try:
        return date_format(localtime(value), 'SHORT_DATE_FORMAT')
    except Exception:  # pylint: disable=broad-except
        return EMPTY_DISPLAY


def _ensure_aware(dt):
    if dt is None:
        return None
    if timezone.is_aware(dt):
        return dt
    return timezone.make_aware(dt, timezone.get_current_timezone())


def normalize_course_filter(course_filter: Optional[str]) -> str:
    if course_filter in COURSE_FILTERS:
        return course_filter
    return COURSE_FILTER_ACTIVE


def get_course_overviews(course_filter: str = COURSE_FILTER_ACTIVE):
    overviews = CourseOverview.objects.all()
    if course_filter == COURSE_FILTER_ACTIVE:
        return CourseOverview.get_courses_by_status(True, False, overviews).order_by('display_name')
    if course_filter == COURSE_FILTER_ARCHIVED:
        return CourseOverview.get_courses_by_status(False, True, overviews).order_by('display_name')
    return overviews.order_by('display_name')


def format_duration(seconds: Optional[float]) -> str:
    if seconds is None:
        return EMPTY_DISPLAY
    days = max(int(seconds // 86400), 0)
    if days >= 30:
        months = max(days // 30, 1)
        return force_str(ngettext(
            '%(months)s month',
            '%(months)s months',
            months,
        ) % {'months': months})
    return force_str(ngettext(
        '%(days)s day',
        '%(days)s days',
        days,
    ) % {'days': days})


def _course_is_archived(overview: CourseOverview, now=None) -> bool:
    now = _ensure_aware(now or timezone.now())
    end = _ensure_aware(overview.end)
    return bool(end and end < now)


def get_course_participant_stats(course_key) -> Dict[str, Any]:
    now = _ensure_aware(timezone.now())
    inactivity_cutoff = now - timedelta(days=DROPOUT_INACTIVITY_DAYS)

    enrollments = list(
        CourseEnrollment.objects.filter(
            course_id=course_key,
            is_active=True,
        ).select_related('user')
    )
    total_enrolled = len(enrollments)
    if not total_enrolled:
        return {
            'total_enrolled': 0,
            'completed_count': 0,
            'average_grade': None,
            'average_grade_display': EMPTY_DISPLAY,
            'average_duration_seconds': None,
            'average_duration_display': EMPTY_DISPLAY,
            'dropped_count': 0,
            'active_count': 0,
        }

    user_ids = [enrollment.user_id for enrollment in enrollments]

    grade_rows = PersistentCourseGrade.objects.filter(
        course_id=course_key,
        user_id__in=user_ids,
    )
    completed_count = grade_rows.filter(passed_timestamp__isnull=False).count()
    average_grade = grade_rows.aggregate(avg=Avg('percent_grade'))['avg']

    last_module_access = {
        row['student_id']: row['last_access']
        for row in StudentModule.objects.filter(
            course_id=course_key,
            student_id__in=user_ids,
        ).values('student_id').annotate(last_access=Max('modified'))
    }

    duration_total_seconds = 0.0
    dropped_count = 0

    for enrollment in enrollments:
        user = enrollment.user
        if user is None:
            dropped_count += 1
            continue

        last_activity = last_module_access.get(user.id) or user.last_login or enrollment.created
        last_activity = _ensure_aware(last_activity)
        enrollment_created = _ensure_aware(enrollment.created)

        if last_activity and last_activity < inactivity_cutoff:
            dropped_count += 1

        if enrollment_created is not None:
            duration_total_seconds += max((now - enrollment_created).total_seconds(), 0.0)

    average_duration_seconds = duration_total_seconds / total_enrolled

    return {
        'total_enrolled': total_enrolled,
        'completed_count': completed_count,
        'average_grade': average_grade,
        'average_grade_display': _format_grade(average_grade),
        'average_duration_seconds': average_duration_seconds,
        'average_duration_display': format_duration(average_duration_seconds),
        'dropped_count': dropped_count,
        'active_count': max(total_enrolled - dropped_count, 0),
    }


def get_platform_summary(course_summaries: List[Dict[str, Any]]) -> Dict[str, Any]:
    courses_count = len(course_summaries)
    total_enrolled = 0
    completed_count = 0
    dropped_count = 0
    active_count = 0
    grade_values: List[float] = []
    duration_values: List[float] = []

    for course in course_summaries:
        participants = course['participants']
        total_enrolled += participants['total_enrolled']
        completed_count += participants['completed_count']
        dropped_count += participants['dropped_count']
        active_count += participants['active_count']
        if participants['average_grade'] is not None and participants['total_enrolled']:
            grade_values.append(float(participants['average_grade']))
        if participants['total_enrolled']:
            duration_values.append(participants.get('average_duration_seconds') or 0.0)

    average_grade = sum(grade_values) / len(grade_values) if grade_values else None
    average_duration_seconds = (
        sum(duration_values) / len(duration_values) if duration_values else None
    )

    return {
        'courses_count': courses_count,
        'total_enrolled': total_enrolled,
        'completed_count': completed_count,
        'dropped_count': dropped_count,
        'active_count': active_count,
        'average_grade_display': _format_grade(average_grade),
        'average_duration_display': format_duration(average_duration_seconds),
    }


def build_analytics_page_context(course_filter: Optional[str] = None) -> Dict[str, Any]:
    normalized_filter = normalize_course_filter(course_filter)
    now = _ensure_aware(timezone.now())
    course_summaries: List[Dict[str, Any]] = []

    for overview in get_course_overviews(normalized_filter):
        course_key = overview.id
        try:
            participants = get_course_participant_stats(course_key)
            enrollment_count = dict(CourseEnrollment.objects.enrollment_counts(course_key))
            course_summaries.append({
                'course_id': course_key,
                'course_anchor': force_str(course_key).replace(':', '-').replace('+', '-').replace('@', '-'),
                'course_display_name': _display(overview.display_name_with_default),
                'course_org': _display(overview.display_org_with_default),
                'course_number': _display(overview.display_number_with_default),
                'course_run': _display(getattr(course_key, 'run', '') or ''),
                'course_start_display': _format_date(overview.start),
                'course_end_display': _format_date(overview.end),
                'short_description': _display(overview.short_description),
                'is_archived': _course_is_archived(overview, now),
                'enrollment_count': enrollment_count,
                'participants': participants,
            })
        except Exception:  # pylint: disable=broad-except
            log.exception('Robbo analytics: failed to build summary for %s', course_key)

    course_summaries.sort(key=lambda item: item['course_display_name'].lower())

    return {
        'course_filter': normalized_filter,
        'platform_summary': get_platform_summary(course_summaries),
        'course_summaries': course_summaries,
    }
