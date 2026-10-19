# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution. See NOTICE at repository root.

"""
Course card progress after the cards: init and the /courses catalog read it from the cache only
(``progressPending``, ``progress_pending``), ``robbo_progress`` builds what is missing
(learner_home.views.RobboProgressView).
"""

from unittest.mock import patch

from django.core.cache import cache
from django.test import RequestFactory
from django.urls import reverse
from opaque_keys.edx.keys import CourseKey
from rest_framework.test import APITestCase

from common.djangoapps.student.tests.factories import UserFactory
from lms.djangoapps.courseware.robbo_catalog import build_robbo_catalog_course_cards
from lms.djangoapps.learner_home.test_views import create_test_enrollment
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from xmodule.modulestore.tests.django_utils import TEST_DATA_SPLIT_MODULESTORE, SharedModuleStoreTestCase

PROGRESS = {'completed': 1, 'total': 4, 'percent': 25}
COMPUTE = 'lms.djangoapps.courseware.robbo_course_progress._compute_progress'


class RobboProgressTest(SharedModuleStoreTestCase, APITestCase):
    """A learner with one enrollment and a staff member."""

    MODULESTORE = TEST_DATA_SPLIT_MODULESTORE
    PASSWORD = 'enigma'

    def setUp(self):
        super().setUp()
        cache.clear()
        self.user = UserFactory(password=self.PASSWORD)
        self.course_id = str(create_test_enrollment(self.user).course_id)
        self.client.login(username=self.user.username, password=self.PASSWORD)

    def init_course_run(self):
        response = self.client.get(reverse('learner_home:initialize'))
        assert response.status_code == 200
        return response.json()['courses'][0]['courseRun']

    def progress(self, **params):
        return self.client.get(reverse('learner_home:robbo_progress'), params)

    @patch(COMPUTE, return_value=PROGRESS)
    def test_init_leaves_uncached_progress_to_robbo_progress(self, compute):
        course_run = self.init_course_run()
        assert course_run['progress'] is None
        assert course_run['progressPending'] is True
        compute.assert_not_called()

        response = self.progress()
        assert response.status_code == 200
        assert response.json() == {
            'progress': {self.course_id: {'completedCount': 1, 'totalCount': 4, 'percent': 25}},
        }
        assert compute.call_count == 1

        # Cached now: the next visit gets the cards with their progress at once.
        course_run = self.init_course_run()
        assert course_run['progress'] == {'completedCount': 1, 'totalCount': 4, 'percent': 25}
        assert course_run['progressPending'] is False
        assert compute.call_count == 1

    @patch(COMPUTE, return_value={'total': 0})
    def test_course_without_units_has_no_progress(self, _compute):
        assert self.progress().json() == {'progress': {self.course_id: None}}
        course_run = self.init_course_run()
        assert course_run['progress'] is None
        assert course_run['progressPending'] is False

    @patch(COMPUTE, return_value=PROGRESS)
    def test_staff_gets_the_progress_of_a_learner(self, _compute):
        staff = UserFactory(is_staff=True, password=self.PASSWORD)
        self.client.login(username=staff.username, password=self.PASSWORD)
        response = self.progress(user=self.user.username)
        assert response.status_code == 200
        assert list(response.json()['progress']) == [self.course_id]

    def test_learner_cannot_get_the_progress_of_another_user(self):
        other = UserFactory()
        assert self.progress(user=other.username).status_code == 403

    def catalog_card(self):
        request = RequestFactory().get('/courses')
        request.user = self.user
        overview = CourseOverview.get_from_id(CourseKey.from_string(self.course_id))
        return build_robbo_catalog_course_cards(request, [overview])[0]

    @patch(COMPUTE, return_value=PROGRESS)
    def test_catalog_leaves_uncached_progress_to_robbo_progress(self, compute):
        card = self.catalog_card()
        assert card['is_enrolled'] is True
        assert card['progress_pending'] is True
        assert 'progress_percent' not in card
        compute.assert_not_called()

        self.progress()
        card = self.catalog_card()
        assert card['progress_percent'] == 25
        assert 'progress_pending' not in card

    def test_needs_login(self):
        self.client.logout()
        assert self.progress().status_code == 401
