# Copyright (C) 2024-2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only

"""
Tests for Robbo global analytics access rules.
"""
from django.test import TestCase
from opaque_keys.edx.keys import CourseKey

from common.djangoapps.student.tests.factories import InstructorFactory, StaffFactory, UserFactory
from lms.djangoapps.robbo_analytics.access import can_access_robbo_global_analytics


class RobboAnalyticsAccessTests(TestCase):
    """
    Access is limited to global staff and course instructors.
    """

    def setUp(self):
        super().setUp()
        self.course_key = CourseKey.from_string('course-v1:edX+DemoX+Demo_Course')
        self.student = UserFactory.create()
        self.staff = StaffFactory.create(course_key=self.course_key)
        self.instructor = InstructorFactory.create(course_key=self.course_key)
        self.admin = UserFactory.create(is_staff=True)

    def test_student_cannot_access(self):
        assert not can_access_robbo_global_analytics(self.student)

    def test_course_staff_cannot_access(self):
        assert not can_access_robbo_global_analytics(self.staff)

    def test_course_instructor_can_access(self):
        assert can_access_robbo_global_analytics(self.instructor)

    def test_global_staff_can_access(self):
        assert can_access_robbo_global_analytics(self.admin)
