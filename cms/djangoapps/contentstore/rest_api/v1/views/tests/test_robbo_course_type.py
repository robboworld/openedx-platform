# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (course type: paid access and paid certificate). See NOTICE at repository root.
"""
Tests for the Studio «Тип курса» API: paid full access (verified mode) and paid certificate.
"""
from unittest.mock import patch

from django.urls import reverse
from rest_framework import status

from cms.djangoapps.contentstore.tests.utils import CourseTestCase
from common.djangoapps.course_modes.models import CourseMode
from common.djangoapps.student.models import CourseEnrollment
from common.djangoapps.student.roles import CourseStaffRole
from common.djangoapps.student.tests.factories import UserFactory
from lms.djangoapps.robbo_certificates.models import CertificateOffer
from lms.djangoapps.robbo_paid_content.models import PaidContentPolicy
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from openedx.core.djangoapps.course_groups.models import CourseUserGroup
from xmodule.modulestore.tests.factories import BlockFactory


class CourseTypeViewTest(CourseTestCase):
    """CourseTypeView: course team reads, platform staff changes."""

    def setUp(self):
        super().setUp()
        CourseOverview.load_from_module_store(self.course.id)  # passing grade 50 % (the default cutoff)
        self.url = reverse('cms.djangoapps.contentstore:v1:robbo_course_type', kwargs={'course_id': self.course.id})

    def _put(self, body, client=None):
        return (client or self.client).put(self.url, body, content_type='application/json')

    def test_free_course(self):
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['can_edit'] is True
        assert response.data['passing_percent'] == 50
        assert response.data['certificate'] == {
            'paid': False, 'price': None, 'min_percent': None, 'free_for_verified': True, 'free_for_cohorts': [],
        }
        assert response.data['full_access'] == {'paid': False, 'price': None, 'learners': 0}

    def test_staff_makes_both_paid(self):
        cohort = CourseUserGroup.objects.create(
            name='B2B', course_id=self.course.id, group_type=CourseUserGroup.COHORT,
        )
        response = self._put({
            'full_access': {'paid': True, 'price': '1990'},
            'certificate': {'paid': True, 'price': 990, 'min_percent': 80, 'free_for_verified': False,
                            'free_for_cohorts': [cohort.id]},
        })
        assert response.status_code == status.HTTP_200_OK, response.data
        assert response.data['full_access']['paid'] and response.data['full_access']['price'] == 1990
        assert response.data['certificate'] == {
            'paid': True, 'price': 990, 'min_percent': 80, 'free_for_verified': False,
            'free_for_cohorts': [cohort.id],
        }
        mode = CourseMode.objects.get(course_id=self.course.id, mode_slug='verified')
        assert (mode.min_price, mode.currency, mode.expiration_datetime) == (1990, 'rub', None)
        assert mode.sku.startswith('ROBBO-VERIFIED-')
        # A free enrollment mode is added, or nobody could enroll without paying
        assert CourseMode.objects.filter(course_id=self.course.id, mode_slug='honor').exists()
        offer = CertificateOffer.objects.get(course_key=self.course.id)
        assert offer.updated_by == self.user and offer.free_for_modes == []

    def test_turning_off(self):
        self._put({'full_access': {'paid': True, 'price': 1990}, 'certificate': {'paid': True, 'price': 990}})
        response = self._put({'full_access': {'paid': False}, 'certificate': {'paid': False}})
        assert response.status_code == status.HTTP_200_OK
        # No paid learners: the mode goes; the offer stays, turned off (its price history is kept)
        assert not CourseMode.objects.filter(course_id=self.course.id, mode_slug='verified').exists()
        assert CertificateOffer.objects.get(course_key=self.course.id).is_enabled is False
        assert response.data['certificate']['paid'] is False
        assert response.data['certificate']['price'] == 990

    def test_turning_off_full_access_with_paid_learners_expires_the_mode(self):
        self._put({'full_access': {'paid': True, 'price': 1990}})
        CourseEnrollment.enroll(UserFactory(), self.course.id, 'verified')
        response = self._put({'full_access': {'paid': False}})
        mode = CourseMode.objects.get(course_id=self.course.id, mode_slug='verified')
        assert mode.expiration_datetime is not None and mode.expiration_datetime_is_explicit
        assert response.data['full_access'] == {'paid': False, 'price': 1990, 'learners': 1}
        # On again: sold with no deadline
        self._put({'full_access': {'paid': True, 'price': 2490}})
        mode.refresh_from_db()
        assert (mode.min_price, mode.expiration_datetime) == (2490, None)

    def test_validation(self):
        for body, text in (
            ({'certificate': {'paid': True, 'price': 0}}, 'Цена'),
            ({'certificate': {'paid': True, 'price': '99.5'}}, 'Цена'),
            ({'full_access': {'paid': True, 'price': 'abc'}}, 'Цена'),
            ({'certificate': {'paid': True, 'price': 990, 'min_percent': 30}}, 'проходного балла курса (50 %)'),
            ({'certificate': {'paid': True, 'price': 990, 'free_for_cohorts': [999999]}}, 'группы этого курса'),
        ):
            response = self._put(body)
            assert response.status_code == status.HTTP_400_BAD_REQUEST, body
            assert text in response.data['error'], response.data
        # Nothing was half-saved
        assert not CertificateOffer.objects.exists()
        assert not CourseMode.objects.filter(course_id=self.course.id, mode_slug='verified').exists()

    def test_course_team_reads_but_cannot_change(self):
        client, author = self.create_non_staff_authed_user_client()
        CourseStaffRole(self.course.id).add_users(author)
        response = client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['can_edit'] is False
        response = self._put({'certificate': {'paid': True, 'price': 990}}, client=client)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert not CertificateOffer.objects.exists()

    def test_outsider_cannot_read(self):
        client, _user = self.create_non_staff_authed_user_client()
        assert client.get(self.url).status_code == status.HTTP_403_FORBIDDEN


class CourseTypePaidContentTest(CourseTestCase):
    """The «Платный контент» part of the course type: policy and the count of locked sections/subsections."""

    def setUp(self):
        super().setUp()
        CourseOverview.load_from_module_store(self.course.id)
        self.url = reverse('cms.djangoapps.contentstore:v1:robbo_course_type', kwargs={'course_id': self.course.id})
        section = BlockFactory.create(parent=self.course, category='chapter', metadata={'robbo_paid_only': True})
        BlockFactory.create(parent=section, category='sequential', metadata={'robbo_paid_only': True})
        BlockFactory.create(parent=self.course, category='chapter')

    def _put(self, body):
        return self.client.put(self.url, body, content_type='application/json')

    def test_defaults(self):
        assert self.client.get(self.url).data['paid_content'] == {
            'enabled': False, 'free_sections': None, 'graded_paid': False, 'display': 'locked',
            'grading': 'zero', 'sections': 2, 'locked': 2,
        }

    @patch('cms.djangoapps.contentstore.outlines.update_outline_from_modulestore')
    def test_save_and_turn_off(self, update_outline):
        with self.captureOnCommitCallbacks(execute=True):
            response = self._put({'paid_content': {
                'enabled': True, 'free_sections': '1', 'graded_paid': True, 'display': 'hidden', 'grading': 'excluded',
            }})
        assert response.status_code == status.HTTP_200_OK, response.data
        assert response.data['paid_content']['enabled'] and response.data['paid_content']['free_sections'] == 1
        policy = PaidContentPolicy.objects.get(course_key=self.course.id)
        assert (policy.graded_paid, policy.display, policy.grading, policy.updated_by) == (
            True, 'hidden', 'excluded', self.user,
        )
        update_outline.assert_called_once_with(self.course.id)
        with self.captureOnCommitCallbacks(execute=True):
            response = self._put({'paid_content': {'enabled': False}})
        assert PaidContentPolicy.objects.get(course_key=self.course.id).is_enabled is False
        assert response.data['paid_content']['free_sections'] == 1  # kept for turning it on again
        assert update_outline.call_count == 2

    def test_validation(self):
        for body, text in (
            ({'enabled': True, 'free_sections': 'много'}, 'целое число'),
            ({'enabled': True, 'display': 'blurred'}, 'показа'),
            ({'enabled': True, 'grading': 'half'}, 'учёта оценок'),
        ):
            response = self._put({'paid_content': body})
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert text in response.data['error']
        assert not PaidContentPolicy.objects.exists()
