# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (paid certificates). See NOTICE at repository root.

"""Tests for paid certificates: the generation filter, purchase state, progress page data."""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import override_settings
from django.utils import timezone
from edx_toggles.toggles.testutils import override_waffle_switch
from openedx_filters.learning.filters import CertificateCreationRequested

from common.djangoapps.course_modes.models import CourseMode
from common.djangoapps.student.models import CourseEnrollment
from common.djangoapps.student.tests.factories import UserFactory
from lms.djangoapps.commerce.models import CommerceConfiguration
from lms.djangoapps.course_home_api.progress.serializers import CertificateDataSerializer
from lms.djangoapps.courseware.views.views import (
    REQUESTING_CERT_DATA,
    ROBBO_PURCHASE_CERT_STATUS,
    _robbo_paid_certificate_data,
)
from lms.djangoapps.robbo_certificates import offers
from lms.djangoapps.robbo_certificates.apps import CERTIFICATE_CREATION_FILTER, _ensure_paid_certificate_filter
from lms.djangoapps.robbo_certificates.models import CertificateEntitlement, CertificateOffer
from lms.djangoapps.robbo_payments.constants import Product
from lms.djangoapps.robbo_payments.models import Order
from openedx.core.djangoapps.course_groups.tests.helpers import CohortFactory, config_course_cohorts
from openedx.core.djangolib.testing.utils import skip_unless_lms
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory

STEP = 'lms.djangoapps.robbo_certificates.filters.RequirePaidCertificate'


def _grade(percent):
    return MagicMock(percent=percent, passed=True)


@skip_unless_lms
@override_settings(ROBBO_PAYMENTS_ENABLED=True)
@override_waffle_switch(offers.PAID_CERTIFICATES, active=True)
@patch('lms.djangoapps.robbo_certificates.offers._on_allowlist', return_value=False)
class PaidCertificateRulesTests(ModuleStoreTestCase):
    """offers.blocking_reason / purchase_state and the generation filter."""

    def setUp(self):
        super().setUp()
        CommerceConfiguration.objects.update_or_create(
            id=1, defaults={'enabled': True, 'checkout_on_ecommerce_service': True},
        )
        self.course = CourseFactory.create()
        self.course_key = self.course.id
        self.user = UserFactory.create()
        CourseEnrollment.enroll(self.user, self.course_key, CourseMode.HONOR)
        self.offer = CertificateOffer.objects.create(course_key=self.course_key, price=Decimal('990.00'))

    def test_not_bought_is_blocked(self, _allowlist):
        assert offers.blocking_reason(self.user, self.course_key, CourseMode.HONOR, _grade(0.9))
        state = offers.purchase_state(self.user, self.course_key, CourseMode.HONOR, _grade(0.9))
        assert (state.state, state.percent) == (offers.AVAILABLE, 90)

    def test_entitlement_lets_through_and_revoked_does_not(self, _allowlist):
        entitlement = offers.grant(self.user, self.course_key, CertificateEntitlement.SOURCE_PAID, 'ROBBO-1')
        assert offers.blocking_reason(self.user, self.course_key, CourseMode.HONOR, _grade(0.9)) is None
        assert offers.purchase_state(self.user, self.course_key, CourseMode.HONOR, _grade(0.9)) is None
        entitlement.revoked_at = timezone.now()
        entitlement.save()
        assert offers.blocking_reason(self.user, self.course_key, CourseMode.HONOR, _grade(0.9))
        # A new purchase restores the right
        offers.grant(self.user, self.course_key, CertificateEntitlement.SOURCE_PAID, 'ROBBO-2')
        assert CertificateEntitlement.objects.get(user=self.user).revoked_at is None

    def test_free_for_verified_by_default(self, _allowlist):
        assert offers.blocking_reason(self.user, self.course_key, CourseMode.VERIFIED, _grade(0.9)) is None

    def test_free_for_cohort(self, _allowlist):
        config_course_cohorts(self.course, is_cohorted=True)
        cohort = CohortFactory(course_id=self.course_key, users=[self.user])
        assert offers.blocking_reason(self.user, self.course_key, CourseMode.HONOR, _grade(0.9))
        self.offer.free_for_cohorts.add(cohort)
        assert offers.blocking_reason(self.user, self.course_key, CourseMode.HONOR, _grade(0.9)) is None

    def test_threshold_applies_to_everyone(self, _allowlist):
        self.offer.min_percent = 80
        self.offer.save()
        assert offers.blocking_reason(self.user, self.course_key, CourseMode.VERIFIED, _grade(0.79))
        state = offers.purchase_state(self.user, self.course_key, CourseMode.HONOR, _grade(0.79))
        assert (state.state, state.percent, state.min_percent) == (offers.BELOW_THRESHOLD, 79, 80)
        assert offers.blocking_reason(self.user, self.course_key, CourseMode.VERIFIED, 0.8) is None

    def test_allowlist_is_never_blocked(self, allowlist):
        allowlist.return_value = True
        assert offers.blocking_reason(self.user, self.course_key, CourseMode.HONOR, _grade(0.9)) is None
        assert offers.purchase_state(self.user, self.course_key, CourseMode.HONOR, _grade(0.9)) is None

    def test_offer_off_switch_off_or_payments_off_is_free(self, _allowlist):
        with override_waffle_switch(offers.PAID_CERTIFICATES, active=False):
            assert offers.blocking_reason(self.user, self.course_key, CourseMode.HONOR, _grade(0.9)) is None
        with override_settings(ROBBO_PAYMENTS_ENABLED=False):
            assert offers.blocking_reason(self.user, self.course_key, CourseMode.HONOR, _grade(0.9)) is None
        self.offer.is_enabled = False
        self.offer.save()
        assert offers.blocking_reason(self.user, self.course_key, CourseMode.HONOR, _grade(0.9)) is None

    def test_recent_pending_order(self, _allowlist):
        order = Order.objects.create(
            user=self.user, course_key=self.course_key, product=Product.CERTIFICATE, sku=self.offer.sku,
            amount=self.offer.price, idempotency_key='pending-1',
        )
        state = offers.purchase_state(self.user, self.course_key, CourseMode.HONOR, _grade(0.9))
        assert (state.state, state.order_number) == (offers.PENDING, order.order_number)
        payload = offers.offer_payload(state)
        assert payload['price_display'] == '990\u00a0₽'
        assert payload['receipt_url'].endswith(f'?order_number={order.order_number}')
        Order.objects.filter(pk=order.pk).update(created_at=timezone.now() - timedelta(hours=1))
        state = offers.purchase_state(self.user, self.course_key, CourseMode.HONOR, _grade(0.9))
        assert state.state == offers.AVAILABLE

    def test_filter_pipeline_blocks_and_lets_through(self, _allowlist):
        with self.assertRaises(CertificateCreationRequested.PreventCertificateCreation):
            CertificateCreationRequested.run_filter(
                user=self.user, course_key=self.course_key, mode=CourseMode.HONOR, status='downloadable',
                grade=_grade(0.9), generation_mode='batch',
            )
        offers.grant(self.user, self.course_key, CertificateEntitlement.SOURCE_STAFF_GRANT)
        result = CertificateCreationRequested.run_filter(
            user=self.user, course_key=self.course_key, mode=CourseMode.HONOR, status='downloadable',
            grade=_grade(0.9), generation_mode='batch',
        )
        assert result[0] == self.user

    def test_filter_fails_closed(self, _allowlist):
        with patch.object(offers, 'blocking_reason', side_effect=RuntimeError('boom')):
            with self.assertRaises(CertificateCreationRequested.PreventCertificateCreation):
                CertificateCreationRequested.run_filter(
                    user=self.user, course_key=self.course_key, mode=CourseMode.HONOR, status='downloadable',
                    grade=_grade(0.9), generation_mode='batch',
                )

    @patch('lms.djangoapps.certificates.generation_handler.generate_certificate.apply_async')
    @patch('lms.djangoapps.certificates.generation_handler._can_generate_regular_certificate', return_value=True)
    def test_platform_generation_is_stopped(self, _can_generate, apply_async, _allowlist):
        from lms.djangoapps.certificates.generation_handler import (
            CertificateGenerationNotAllowed,
            generate_certificate_task,
        )
        with patch('lms.djangoapps.certificates.generation_handler._get_course_grade', return_value=_grade(0.9)):
            with self.assertRaises(CertificateGenerationNotAllowed):
                generate_certificate_task(self.user, self.course_key)
            assert not apply_async.called
            offers.grant(self.user, self.course_key, CertificateEntitlement.SOURCE_PAID, 'ROBBO-3')
            assert generate_certificate_task(self.user, self.course_key)
            assert apply_async.called

    def test_progress_page_data(self, _allowlist):
        self.offer.min_percent = 50
        self.offer.save()
        cert_data = _robbo_paid_certificate_data(self.user, self.course, CourseMode.HONOR, _grade(0.84))
        assert cert_data.cert_status == ROBBO_PURCHASE_CERT_STATUS
        data = CertificateDataSerializer(cert_data).data
        assert data['robbo_offer']['state'] == offers.AVAILABLE
        assert data['robbo_offer']['percent'] == 84
        assert data['robbo_offer']['min_percent'] == 50
        assert data['robbo_offer']['checkout_url'] == f'/robbo/certificates/buy/{self.course_key}/'
        assert CertificateDataSerializer(REQUESTING_CERT_DATA).data['robbo_offer'] is None


@skip_unless_lms
class FilterConfigTests(ModuleStoreTestCase):
    """The step stays in the pipeline even if a deployment's YAML replaces OPEN_EDX_FILTERS_CONFIG."""

    def test_step_in_default_settings(self):
        from django.conf import settings
        assert STEP in settings.OPEN_EDX_FILTERS_CONFIG[CERTIFICATE_CREATION_FILTER]['pipeline']

    def test_step_added_to_replaced_config(self):
        config = {'org.openedx.learning.course.enrollment.started.v1': {'pipeline': ['x.Y']}}
        with override_settings(OPEN_EDX_FILTERS_CONFIG=config):
            _ensure_paid_certificate_filter()
            from django.conf import settings
            assert settings.OPEN_EDX_FILTERS_CONFIG[CERTIFICATE_CREATION_FILTER]['pipeline'] == [STEP]
            assert settings.OPEN_EDX_FILTERS_CONFIG['org.openedx.learning.course.enrollment.started.v1']
