# Copyright (C) 2024-2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only

"""
Tests for Robbo global analytics services.
"""
from datetime import datetime
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from opaque_keys.edx.keys import CourseKey

from lms.djangoapps.robbo_analytics.services import (
    COURSE_FILTER_ACTIVE,
    COURSE_FILTER_ARCHIVED,
    COURSE_FILTER_ALL,
    EMPTY_DISPLAY,
    _ensure_aware,
    build_analytics_page_context,
    format_duration,
    get_course_participant_stats,
    get_platform_summary,
    normalize_course_filter,
)


class RobboAnalyticsServicesTests(TestCase):
    def test_normalize_course_filter_defaults_to_active(self):
        assert normalize_course_filter(None) == COURSE_FILTER_ACTIVE
        assert normalize_course_filter('unknown') == COURSE_FILTER_ACTIVE
        assert normalize_course_filter(COURSE_FILTER_ALL) == COURSE_FILTER_ALL

    def test_format_duration(self):
        assert format_duration(None) == EMPTY_DISPLAY
        assert format_duration(86400)

    def test_ensure_aware_handles_naive_datetime(self):
        naive = datetime(2024, 1, 1, 12, 0, 0)
        aware = _ensure_aware(naive)
        assert timezone.is_aware(aware)

    def test_get_course_participant_stats_empty_course(self):
        course_key = CourseKey.from_string('course-v1:edX+DemoX+Demo_Course')
        stats = get_course_participant_stats(course_key)
        assert stats['total_enrolled'] == 0
        assert stats['active_count'] == 0

    def test_get_platform_summary_aggregates(self):
        summaries = [
            {
                'participants': {
                    'total_enrolled': 10,
                    'completed_count': 3,
                    'dropped_count': 2,
                    'active_count': 8,
                    'average_grade': 75.0,
                    'average_duration_seconds': 86400.0,
                },
            },
        ]
        summary = get_platform_summary(summaries)
        assert summary['courses_count'] == 1
        assert summary['total_enrolled'] == 10

    @patch('lms.djangoapps.robbo_analytics.services.get_course_overviews')
    @patch('lms.djangoapps.robbo_analytics.services.get_course_participant_stats')
    @patch('lms.djangoapps.robbo_analytics.services.CourseEnrollment.objects.enrollment_counts')
    def test_build_analytics_page_context(self, mock_counts, mock_stats, mock_overviews):
        course_key = CourseKey.from_string('course-v1:edX+DemoX+Demo_Course')
        overview = type('Overview', (), {
            'id': course_key,
            'display_name_with_default': 'Demo Course',
            'display_org_with_default': 'edX',
            'display_number_with_default': 'DemoX',
            'start': timezone.now(),
            'end': None,
            'short_description': 'Short',
        })()
        mock_overviews.return_value = [overview]
        mock_stats.return_value = get_course_participant_stats(course_key)
        mock_counts.return_value = {'total': 0}

        context = build_analytics_page_context(COURSE_FILTER_ARCHIVED)
        assert context['course_filter'] == COURSE_FILTER_ARCHIVED
        assert len(context['course_summaries']) == 1
