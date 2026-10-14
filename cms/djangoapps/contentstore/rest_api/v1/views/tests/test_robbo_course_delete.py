# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (course deletion in Studio). See NOTICE at repository root.
"""
Tests for deleting a course from the Studio home page.
"""
from django.urls import reverse
from rest_framework import status

from cms.djangoapps.contentstore.tests.utils import CourseTestCase
from common.djangoapps.student.models import CourseEnrollment
from common.djangoapps.student.roles import CourseInstructorRole
from common.djangoapps.student.tests.factories import UserFactory
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from xmodule.modulestore.django import modulestore


class CourseDeleteViewTest(CourseTestCase):
    """
    Tests for CourseDeleteView.
    """
    # CourseOverview is removed by the course_deleted signal handler.
    ENABLED_SIGNALS = ['course_deleted']

    def setUp(self):
        super().setUp()
        self.url = reverse(
            'cms.djangoapps.contentstore:v1:robbo_course_delete',
            kwargs={'course_id': self.course.id},
        )

    def test_summary(self):
        learner, dropped = UserFactory(), UserFactory()
        CourseEnrollment.enroll(learner, self.course.id)
        CourseEnrollment.enroll(dropped, self.course.id)
        CourseEnrollment.unenroll(dropped, self.course.id)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertDictEqual(response.data, {
            'course_id': str(self.course.id),
            'display_name': self.course.display_name,
            'enrollment_count': 1,
        })

    def test_delete(self):
        instructor = UserFactory()
        CourseInstructorRole(self.course.id).add_users(instructor)
        enrollment = CourseEnrollment.enroll(UserFactory(), self.course.id)

        response = self.client.delete(self.url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertIsNone(modulestore().get_course(self.course.id))
        self.assertFalse(CourseOverview.objects.filter(id=self.course.id).exists())
        self.assertFalse(CourseInstructorRole(self.course.id).has_user(instructor))
        self.assertTrue(CourseEnrollment.objects.filter(pk=enrollment.pk).exists())
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_404_NOT_FOUND)

    def test_course_team_cannot_delete(self):
        client, user = self.create_non_staff_authed_user_client()
        CourseInstructorRole(self.course.id).add_users(user)

        self.assertEqual(client.get(self.url).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(client.delete(self.url).status_code, status.HTTP_403_FORBIDDEN)
        self.assertIsNotNone(modulestore().get_course(self.course.id))

    def test_unknown_course(self):
        url = reverse(
            'cms.djangoapps.contentstore:v1:robbo_course_delete',
            kwargs={'course_id': 'course-v1:Robbo+Missing+2026'},
        )
        self.assertEqual(self.client.delete(url).status_code, status.HTTP_404_NOT_FOUND)
