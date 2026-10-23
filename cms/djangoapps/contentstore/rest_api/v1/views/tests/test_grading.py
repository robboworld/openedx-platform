"""
Unit tests for course grading views.

Modifications Copyright (C) 2026 Robbo. See NOTICE at repository root.
"""
import json
from unittest.mock import patch

import ddt
from django.urls import reverse
from rest_framework import status

from cms.djangoapps.contentstore.tests.utils import CourseTestCase
from cms.djangoapps.contentstore.utils import get_proctored_exam_settings_url
from cms.djangoapps.models.settings.course_grading import CourseGradingModel
from openedx.core.djangoapps.credit.tests.factories import CreditCourseFactory
from xmodule.modulestore.tests.factories import BlockFactory

from ...mixins import PermissionAccessMixin


@ddt.ddt
class CourseGradingViewTest(CourseTestCase, PermissionAccessMixin):
    """
    Tests for CourseGradingView.
    """

    def setUp(self):
        super().setUp()
        self.url = reverse(
            "cms.djangoapps.contentstore:v1:course_grading",
            kwargs={"course_id": self.course.id},
        )

    def test_course_grading_response(self):
        """Check successful response content"""
        response = self.client.get(self.url)
        grading_data = CourseGradingModel.fetch(self.course.id)

        expected_response = {
            "mfe_proctored_exam_settings_url": get_proctored_exam_settings_url(
                self.course.id
            ),
            "course_assignment_lists": {},
            "unscored_assignment_lists": {},
            "course_details": grading_data.__dict__,
            "show_credit_eligibility": False,
            "is_credit_course": False,
            "default_grade_designations": ['A', 'B', 'C', 'D'],
        }

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertDictEqual(expected_response, response.data)

    def test_unscored_assignment_lists(self):
        """
        Robbo: graded subsections without anything that gives points are listed by assignment type.
        """
        section = BlockFactory.create(parent=self.course, category='chapter', display_name='Section')
        empty = BlockFactory.create(
            parent=section, category='sequential', display_name='Empty', format='Homework', graded=True,
        )
        BlockFactory.create(parent=empty, category='vertical', display_name='Unit')
        html_only = BlockFactory.create(
            parent=section, category='sequential', display_name='Text', format='Homework', graded=True,
        )
        BlockFactory.create(
            parent=BlockFactory.create(parent=html_only, category='vertical'), category='html',
        )
        zero_weight = BlockFactory.create(
            parent=section, category='sequential', display_name='Zero', format='Exam', graded=True,
        )
        BlockFactory.create(
            parent=BlockFactory.create(parent=zero_weight, category='vertical'), category='problem', weight=0,
        )
        scored = BlockFactory.create(
            parent=section, category='sequential', display_name='Scored', format='Homework', graded=True,
        )
        BlockFactory.create(
            parent=BlockFactory.create(parent=scored, category='vertical'), category='problem',
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["course_assignment_lists"]["Homework"],
            ['Section - Empty', 'Section - Text', 'Section - Scored'],
        )
        self.assertDictEqual(
            response.data["unscored_assignment_lists"],
            {'Homework': ['Section - Empty', 'Section - Text'], 'Exam': ['Section - Zero']},
        )

    @patch("django.conf.settings.DEFAULT_GRADE_DESIGNATIONS", ['A', 'B'])
    def test_default_grade_designations_setting(self):
        """
        Check that DEFAULT_GRADE_DESIGNATIONS setting reflects correctly in API.
        """
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(['A', 'B'], response.data["default_grade_designations"])

    @patch.dict("django.conf.settings.FEATURES", {"ENABLE_CREDIT_ELIGIBILITY": True})
    def test_credit_eligibility_setting(self):
        """
        Make sure if the feature flag is enabled we have enabled values in response.
        """
        _ = CreditCourseFactory(course_key=self.course.id, enabled=True)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["show_credit_eligibility"])
        self.assertTrue(response.data["is_credit_course"])

    def test_post_permissions_unauthenticated(self):
        """
        Test that an error is returned in the absence of auth credentials.
        """
        self.client.logout()
        response = self.client.post(self.url)
        error = self.get_and_check_developer_response(response)
        self.assertEqual(error, "Authentication credentials were not provided.")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_post_permissions_unauthorized(self):
        """
        Test that an error is returned if the user is unauthorised.
        """
        client, _ = self.create_non_staff_authed_user_client()
        response = client.post(self.url)
        error = self.get_and_check_developer_response(response)
        self.assertEqual(error, "You do not have permission to perform this action.")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch(
        "openedx.core.djangoapps.credit.tasks.update_credit_course_requirements.delay"
    )
    def test_post_course_grading(self, mock_update_credit_course_requirements):
        """Check successful request with called task"""
        request_data = {
            "graders": [
                {
                    "type": "Homework",
                    "min_count": 1,
                    "drop_count": 0,
                    "short_label": "",
                    "weight": 100,
                    "id": 0,
                }
            ],
            "grade_cutoffs": {"A": 0.75, "B": 0.63, "C": 0.57, "D": 0.5},
            "grace_period": {"hours": 12, "minutes": 0},
            "minimum_grade_credit": 0.7,
            "is_credit_course": True,
        }
        response = self.client.post(
            path=self.url,
            data=json.dumps(request_data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_update_credit_course_requirements.assert_called_once()
