# Copyright (C) 2024-2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (YooKassa checkout). See NOTICE at repository root.

"""Tests for Robbo payments."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import ddt
from django.test import Client, RequestFactory, override_settings
from django.urls import reverse

from common.djangoapps.course_modes.models import CourseMode
from common.djangoapps.course_modes.tests.factories import CourseModeFactory
from common.djangoapps.student.models import CourseEnrollment
from common.djangoapps.student.tests.factories import TEST_PASSWORD, UserFactory
from lms.djangoapps.commerce.models import CommerceConfiguration
from lms.djangoapps.robbo_payments.constants import OrderStatus
from lms.djangoapps.robbo_payments.models import Order
from lms.djangoapps.robbo_payments.services.catalog import ProductNotFound, get_first_sku_from_query, resolve_verified_product
from lms.djangoapps.robbo_payments.services.fulfillment import fulfill_verified_upgrade
from openedx.core.djangolib.testing.utils import skip_unless_lms
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory


def _enable_robbo_commerce():
    CommerceConfiguration.objects.update_or_create(
        id=1,
        defaults={
            'enabled': True,
            'checkout_on_ecommerce_service': True,
            'basket_checkout_page': '/basket/add/',
        },
    )


@skip_unless_lms
@ddt.ddt
class CatalogTests(ModuleStoreTestCase):
    """Tests for catalog resolution."""

    def setUp(self):
        super().setUp()
        self.course = CourseFactory.create()
        self.course_key = self.course.id
        CourseModeFactory.create(course_id=self.course_key, mode_slug=CourseMode.AUDIT)
        CourseModeFactory.create(
            course_id=self.course_key,
            mode_slug=CourseMode.VERIFIED,
            sku='TEST-SKU-001',
            min_price=1990,
            currency='rub',
        )

    def test_resolve_verified_product(self):
        product = resolve_verified_product(str(self.course_key), 'TEST-SKU-001')
        assert product.amount == Decimal('1990.00')
        assert product.currency == 'RUB'
        assert product.sku == 'TEST-SKU-001'

    def test_sku_mismatch_raises(self):
        with self.assertRaises(ProductNotFound):
            resolve_verified_product(str(self.course_key), 'WRONG-SKU')

    @ddt.data(['SKU-A', 'SKU-B'], 'SKU-A')
    def test_get_first_sku_from_query(self, value):
        assert get_first_sku_from_query(value) == 'SKU-A'


@skip_unless_lms
class FulfillmentTests(ModuleStoreTestCase):
    """Tests for verified upgrade fulfillment."""

    def setUp(self):
        super().setUp()
        self.user = UserFactory.create()
        self.course = CourseFactory.create()
        self.course_key = self.course.id
        CourseModeFactory.create(course_id=self.course_key, mode_slug=CourseMode.AUDIT)
        CourseModeFactory.create(
            course_id=self.course_key,
            mode_slug=CourseMode.VERIFIED,
            sku='TEST-SKU-002',
            min_price=500,
            currency='rub',
        )
        CourseEnrollment.enroll(self.user, self.course_key, CourseMode.AUDIT)

    def test_fulfill_upgrades_audit_to_verified(self):
        order = Order.objects.create(
            user=self.user,
            course_key=self.course_key,
            sku='TEST-SKU-002',
            amount=Decimal('500.00'),
            currency='RUB',
            idempotency_key='test-key-1',
        )
        fulfill_verified_upgrade(order)
        order.refresh_from_db()
        enrollment = CourseEnrollment.get_enrollment(self.user, self.course_key)
        assert order.status == OrderStatus.PAID
        assert enrollment.mode == CourseMode.VERIFIED

    def test_fulfill_is_idempotent(self):
        order = Order.objects.create(
            user=self.user,
            course_key=self.course_key,
            sku='TEST-SKU-002',
            amount=Decimal('500.00'),
            currency='RUB',
            status=OrderStatus.PAID,
            idempotency_key='test-key-2',
        )
        fulfill_verified_upgrade(order)
        enrollment = CourseEnrollment.get_enrollment(self.user, self.course_key)
        assert enrollment.mode == CourseMode.AUDIT


@skip_unless_lms
@override_settings(
    ROBBO_PAYMENTS_ENABLED=True,
    YOOKASSA_SHOP_ID='shop-id',
    YOOKASSA_SECRET_KEY='secret',
)
class CheckoutViewTests(ModuleStoreTestCase):
    """HTTP tests for checkout entry point."""

    def setUp(self):
        super().setUp()
        _enable_robbo_commerce()
        self.client = Client()
        self.user = UserFactory.create()
        self.client.login(username=self.user.username, password=TEST_PASSWORD)
        self.course = CourseFactory.create()
        self.course_key = self.course.id
        CourseModeFactory.create(course_id=self.course_key, mode_slug=CourseMode.AUDIT)
        CourseModeFactory.create(
            course_id=self.course_key,
            mode_slug=CourseMode.VERIFIED,
            sku='TEST-SKU-003',
            min_price=1000,
            currency='rub',
        )
        CourseEnrollment.enroll(self.user, self.course_key, CourseMode.AUDIT)

    def test_checkout_get_renders(self):
        url = reverse('robbo_payments:basket_add')
        response = self.client.get(url, {'sku': 'TEST-SKU-003', 'course_run_key': str(self.course_key)})
        assert response.status_code == 200
        assert b'\xd0\xaeKassa' in response.content or b'YooKassa' in response.content

    @patch('lms.djangoapps.robbo_payments.views.checkout.create_redirect_payment')
    def test_checkout_post_redirects_to_yookassa(self, mock_create):
        mock_create.return_value = 'https://yookassa.test/pay'
        url = reverse('robbo_payments:basket_add')
        response = self.client.post(url, {'sku': 'TEST-SKU-003', 'course_run_key': str(self.course_key)})
        assert response.status_code == 302
        assert response['Location'] == 'https://yookassa.test/pay'
        assert Order.objects.filter(user=self.user, course_key=self.course_key).exists()


@skip_unless_lms
@override_settings(ROBBO_PAYMENTS_ENABLED=True)
class WebhookViewTests(ModuleStoreTestCase):
    """Webhook handler tests."""

    def setUp(self):
        super().setUp()
        _enable_robbo_commerce()
        self.client = Client()
        self.user = UserFactory.create()
        self.course = CourseFactory.create()
        self.course_key = self.course.id
        CourseModeFactory.create(course_id=self.course_key, mode_slug=CourseMode.AUDIT)
        CourseModeFactory.create(
            course_id=self.course_key,
            mode_slug=CourseMode.VERIFIED,
            sku='TEST-SKU-004',
            min_price=1000,
            currency='rub',
        )
        CourseEnrollment.enroll(self.user, self.course_key, CourseMode.AUDIT)
        self.order = Order.objects.create(
            user=self.user,
            course_key=self.course_key,
            sku='TEST-SKU-004',
            amount=Decimal('1000.00'),
            currency='RUB',
            idempotency_key='webhook-key-1',
            yookassa_payment_id='pay-123',
        )

    @patch('lms.djangoapps.robbo_payments.views.webhook.is_trusted_webhook_ip', return_value=True)
    @patch('lms.djangoapps.robbo_payments.views.webhook.parse_webhook_notification')
    def test_payment_succeeded_webhook_fulfills(self, mock_parse, _mock_ip):
        notification = MagicMock()
        notification.event = 'payment.succeeded'
        notification.object = MagicMock(id='pay-123', metadata={'order_number': self.order.order_number})
        mock_parse.return_value = notification

        url = reverse('robbo_payments:yookassa_webhook')
        response = self.client.post(
            url,
            data='{}',
            content_type='application/json',
        )
        assert response.status_code == 200
        self.order.refresh_from_db()
        enrollment = CourseEnrollment.get_enrollment(self.user, self.course_key)
        assert self.order.status == OrderStatus.PAID
        assert enrollment.mode == CourseMode.VERIFIED


@skip_unless_lms
@override_settings(
    ROBBO_PAYMENTS_ENABLED=True,
    YOOKASSA_SHOP_ID='shop-id',
    YOOKASSA_SECRET_KEY='secret',
)
class ReceiptSyncTests(ModuleStoreTestCase):
    """Receipt page syncs pending orders when webhooks are unavailable."""

    def setUp(self):
        super().setUp()
        _enable_robbo_commerce()
        self.client = Client()
        self.user = UserFactory.create()
        self.client.login(username=self.user.username, password=TEST_PASSWORD)
        self.course = CourseFactory.create()
        self.course_key = self.course.id
        CourseModeFactory.create(course_id=self.course_key, mode_slug=CourseMode.AUDIT)
        CourseModeFactory.create(
            course_id=self.course_key,
            mode_slug=CourseMode.VERIFIED,
            sku='TEST-SKU-005',
            min_price=1000,
            currency='rub',
        )
        CourseEnrollment.enroll(self.user, self.course_key, CourseMode.AUDIT)
        self.order = Order.objects.create(
            user=self.user,
            course_key=self.course_key,
            sku='TEST-SKU-005',
            amount=Decimal('1000.00'),
            currency='RUB',
            idempotency_key='receipt-sync-key-1',
            yookassa_payment_id='pay-receipt-sync',
        )

    @patch('lms.djangoapps.robbo_payments.services.sync.get_payment')
    def test_receipt_sync_fulfills_succeeded_payment(self, mock_get_payment):
        mock_get_payment.return_value = MagicMock(status='succeeded')
        url = reverse('robbo_payments:receipt')
        response = self.client.get(url, {'order_number': self.order.order_number})
        assert response.status_code == 200
        self.order.refresh_from_db()
        enrollment = CourseEnrollment.get_enrollment(self.user, self.course_key)
        assert self.order.status == OrderStatus.PAID
        assert enrollment.mode == CourseMode.VERIFIED
        assert 'Полный доступ к курсу активирован'.encode() in response.content
