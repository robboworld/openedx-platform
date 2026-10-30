# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (paid certificates). See NOTICE at repository root.

"""Tests for paid certificate checkout, fulfillment and receipt."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import Client, override_settings
from django.urls import reverse
from edx_toggles.toggles.testutils import override_waffle_switch

from common.djangoapps.course_modes.models import CourseMode
from common.djangoapps.student.models import CourseEnrollment
from common.djangoapps.student.tests.factories import TEST_PASSWORD, UserFactory
from lms.djangoapps.commerce.models import CommerceConfiguration
from lms.djangoapps.robbo_certificates import offers
from lms.djangoapps.robbo_certificates.models import CertificateEntitlement, CertificateOffer
from lms.djangoapps.robbo_payments.constants import OrderStatus, Product
from lms.djangoapps.robbo_payments.models import Order
from lms.djangoapps.robbo_payments.services.fulfillment import fulfill_order
from openedx.core.djangolib.testing.utils import skip_unless_lms
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory

GRADE_FACTORY = 'lms.djangoapps.robbo_payments.views.certificate.CourseGradeFactory'
GENERATE = 'lms.djangoapps.robbo_certificates.offers.generate_certificate'


def _grade(percent, passed=True):
    return MagicMock(percent=percent, passed=passed)


@skip_unless_lms
@override_settings(ROBBO_PAYMENTS_ENABLED=True, YOOKASSA_SHOP_ID='shop-id', YOOKASSA_SECRET_KEY='secret')
@override_waffle_switch(offers.PAID_CERTIFICATES, active=True)
@patch('lms.djangoapps.robbo_certificates.offers._on_allowlist', return_value=False)
class CertificateCheckoutTests(ModuleStoreTestCase):
    """/robbo/certificates/buy/<course_id>/ → YooKassa → webhook / receipt → right + generation."""

    def setUp(self):
        super().setUp()
        CommerceConfiguration.objects.update_or_create(
            id=1, defaults={'enabled': True, 'checkout_on_ecommerce_service': True},
        )
        self.client = Client()
        self.user = UserFactory.create()
        self.client.login(username=self.user.username, password=TEST_PASSWORD)
        self.course = CourseFactory.create(display_name='Робототехника', run='2026')
        self.course_key = self.course.id
        CourseEnrollment.enroll(self.user, self.course_key, CourseMode.HONOR)
        self.offer = CertificateOffer.objects.create(course_key=self.course_key, price=Decimal('990.00'))
        self.url = reverse('robbo_payments:certificate_checkout', kwargs={'course_id': str(self.course_key)})

    def _cert_order(self, **kwargs):
        defaults = {
            'user': self.user, 'course_key': self.course_key, 'product': Product.CERTIFICATE,
            'sku': self.offer.sku, 'amount': self.offer.price, 'idempotency_key': 'cert-key-1',
            'yookassa_payment_id': 'pay-cert-1',
        }
        defaults.update(kwargs)
        return Order.objects.create(**defaults)

    @patch(GRADE_FACTORY)
    def test_get_shows_course_and_price(self, grade_factory, _allowlist):
        grade_factory.return_value.read.return_value = _grade(0.84)
        response = self.client.get(self.url)
        self.assertContains(response, '990\u00a0₽')
        self.assertContains(response, 'Course completion certificate')
        self.assertNotContains(response, '84 %')
        self.assertContains(response, 'Робототехника')
        self.assertNotContains(response, 'name="sku"')

    @patch(GRADE_FACTORY)
    def test_not_passed_goes_to_progress(self, grade_factory, _allowlist):
        grade_factory.return_value.read.return_value = _grade(0.3, passed=False)
        response = self.client.get(self.url)
        assert response.status_code == 302
        assert response['Location'].endswith('/progress')

    @patch(GRADE_FACTORY)
    def test_already_bought_goes_to_progress(self, grade_factory, _allowlist):
        grade_factory.return_value.read.return_value = _grade(0.84)
        offers.grant(self.user, self.course_key, CertificateEntitlement.SOURCE_PAID, 'ROBBO-X')
        response = self.client.post(self.url)
        assert response.status_code == 302
        assert response['Location'].endswith('/progress')
        assert not Order.objects.exists()

    def test_no_offer_is_not_for_sale(self, _allowlist):
        self.offer.is_enabled = False
        self.offer.save()
        response = self.client.get(self.url)
        self.assertContains(response, 'NOT-FOUND')

    def test_not_enrolled(self, _allowlist):
        CourseEnrollment.unenroll(self.user, self.course_key)
        response = self.client.get(self.url)
        self.assertContains(response, 'ACCESS-DENIED')

    @patch('lms.djangoapps.robbo_payments.views.certificate.create_redirect_payment')
    @patch(GRADE_FACTORY)
    def test_post_creates_certificate_order(self, grade_factory, create_payment, _allowlist):
        grade_factory.return_value.read.return_value = _grade(0.84)
        create_payment.return_value = 'https://yookassa.test/pay'
        response = self.client.post(self.url, {'amount': '1'})  # the price never comes from the client
        assert response['Location'] == 'https://yookassa.test/pay'
        order = Order.objects.get()
        assert (order.product, order.amount, order.sku) == (Product.CERTIFICATE, Decimal('990.00'), self.offer.sku)
        assert create_payment.call_args[0][1] == 'Certificate: Робототехника'

    @patch('lms.djangoapps.robbo_payments.services.sync.get_payment')
    @patch('lms.djangoapps.robbo_payments.views.certificate.create_redirect_payment')
    @patch(GRADE_FACTORY)
    def test_post_with_payment_done_in_another_tab(self, grade_factory, create_payment, get_payment, _allowlist):
        grade_factory.return_value.read.return_value = _grade(0.84)
        order = self._cert_order()
        get_payment.return_value = MagicMock(status='succeeded')
        with patch(GENERATE):
            response = self.client.post(self.url)
        assert response['Location'].endswith(f'?order_number={order.order_number}')
        assert not create_payment.called
        assert Order.objects.count() == 1

    @patch(GENERATE)
    def test_webhook_grants_and_generates(self, generate, _allowlist):
        order = self._cert_order()
        notification = MagicMock(event='payment.succeeded')
        notification.object = MagicMock(id='pay-cert-1', metadata={'order_number': order.order_number})
        with patch('lms.djangoapps.robbo_payments.views.webhook.is_trusted_webhook_ip', return_value=True), \
                patch('lms.djangoapps.robbo_payments.views.webhook.parse_webhook_notification',
                      return_value=notification), \
                self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse('robbo_payments:yookassa_webhook'), data='{}', content_type='application/json',
            )
        assert response.status_code == 200
        order.refresh_from_db()
        assert order.status == OrderStatus.PAID
        entitlement = CertificateEntitlement.objects.get(user=self.user, course_key=self.course_key)
        assert (entitlement.source, entitlement.order_number) == ('paid', order.order_number)
        generate.assert_called_once_with(self.user, self.course_key)
        # The enrollment is not upgraded: a certificate is not course access
        assert CourseEnrollment.get_enrollment(self.user, self.course_key).mode == CourseMode.HONOR

    @patch(GENERATE)
    def test_fulfill_twice_is_idempotent(self, generate, _allowlist):
        order = self._cert_order()
        with self.captureOnCommitCallbacks(execute=True):
            fulfill_order(order)
        with self.captureOnCommitCallbacks(execute=True):
            fulfill_order(order)
        assert CertificateEntitlement.objects.count() == 1
        assert generate.call_count == 1

    @patch(GENERATE)
    def test_receipt_for_certificate(self, _generate, _allowlist):
        order = self._cert_order(status=OrderStatus.PAID)
        response = self.client.get(reverse('robbo_payments:receipt'), {'order_number': order.order_number})
        self.assertContains(response, 'The certificate will appear on the Progress page')
        self.assertContains(response, 'Open the Progress page')
