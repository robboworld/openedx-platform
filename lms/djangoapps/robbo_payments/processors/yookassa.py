# Copyright (C) 2024-2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (YooKassa checkout). See NOTICE at repository root.

"""YooKassa payment processor (sole provider for Robbo commerce v1)."""

import logging
import uuid
from decimal import Decimal
from typing import Any, Dict, Optional
from urllib.parse import urljoin

from django.conf import settings
from django.urls import reverse

from ..models import Order

log = logging.getLogger(__name__)


class YooKassaNotConfigured(Exception):
    """YooKassa credentials are missing."""


class YooKassaPaymentError(Exception):
    """Payment creation failed."""


def is_yookassa_configured() -> bool:
    """Return True when shop credentials are present."""
    return bool(getattr(settings, 'YOOKASSA_SHOP_ID', '') and getattr(settings, 'YOOKASSA_SECRET_KEY', ''))


def _configure_client():
    """Configure the YooKassa SDK from Django settings."""
    from yookassa import Configuration

    shop_id = getattr(settings, 'YOOKASSA_SHOP_ID', '')
    secret_key = getattr(settings, 'YOOKASSA_SECRET_KEY', '')
    if not shop_id or not secret_key:
        raise YooKassaNotConfigured('YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY must be set')
    Configuration.configure(shop_id, secret_key)


def _build_receipt(order: Order, product_description: str, customer_email: str) -> Dict[str, Any]:
    """Build 54-FZ receipt payload for YooKassa."""
    vat_code = getattr(settings, 'ROBBO_PAYMENTS_RECEIPT_VAT_CODE', 1)
    payment_subject = getattr(settings, 'ROBBO_PAYMENTS_RECEIPT_PAYMENT_SUBJECT', 'service')
    payment_mode = getattr(settings, 'ROBBO_PAYMENTS_RECEIPT_PAYMENT_MODE', 'full_payment')

    receipt: Dict[str, Any] = {
        'items': [
            {
                'description': product_description[:128],
                'quantity': '1.00',
                'amount': {
                    'value': f'{order.amount:.2f}',
                    'currency': order.currency,
                },
                'vat_code': vat_code,
                'payment_mode': payment_mode,
                'payment_subject': payment_subject,
            }
        ],
    }
    if customer_email:
        receipt['customer'] = {'email': customer_email}
    return receipt


def build_return_url(order: Order, request) -> str:
    """Absolute URL for YooKassa redirect after payment."""
    path = reverse('robbo_payments:receipt')
    receipt_url = request.build_absolute_uri(f'{path}?order_number={order.order_number}')
    return receipt_url


def create_redirect_payment(order: Order, product_description: str, customer_email: str, request) -> str:
    """
    Create a YooKassa payment and return the confirmation redirect URL.

    Raises YooKassaNotConfigured or YooKassaPaymentError on failure.
    """
    _configure_client()
    from yookassa import Payment

    idempotence_key = order.idempotency_key
    payload: Dict[str, Any] = {
        'amount': {
            'value': f'{order.amount:.2f}',
            'currency': order.currency,
        },
        'confirmation': {
            'type': 'redirect',
            'return_url': build_return_url(order, request),
        },
        'capture': True,
        'description': product_description[:128],
        'metadata': {
            'order_number': order.order_number,
            'course_run_key': str(order.course_key),
            'user_id': str(order.user_id),
        },
    }

    if getattr(settings, 'ROBBO_PAYMENTS_SEND_RECEIPT', True):
        payload['receipt'] = _build_receipt(order, product_description, customer_email)

    try:
        payment = Payment.create(payload, idempotence_key)
    except Exception as exc:
        log.exception('YooKassa payment creation failed for order %s', order.order_number)
        raise YooKassaPaymentError(str(exc)) from exc

    confirmation_url = payment.confirmation.confirmation_url
    payment_id = payment.id
    Order.objects.filter(pk=order.pk).update(yookassa_payment_id=payment_id)
    order.yookassa_payment_id = payment_id
    return confirmation_url


def parse_webhook_notification(body: bytes) -> Any:
    """Parse a YooKassa webhook JSON body into a notification object."""
    import json

    from yookassa.domain.notification import WebhookNotificationFactory

    event_json = json.loads(body.decode('utf-8') if isinstance(body, bytes) else body)
    return WebhookNotificationFactory().create(event_json)


def get_payment(payment_id: str) -> Any:
    """Fetch payment details from YooKassa."""
    _configure_client()
    from yookassa import Payment

    try:
        return Payment.find_one(payment_id)
    except Exception as exc:
        log.exception('YooKassa payment lookup failed for payment_id=%s', payment_id)
        raise YooKassaPaymentError(str(exc)) from exc


def is_trusted_webhook_ip(ip_address: Optional[str]) -> bool:
    """Validate webhook source IP using YooKassa SDK helper."""
    if not ip_address:
        return False
    from yookassa.domain.common import SecurityHelper

    return SecurityHelper().is_ip_trusted(ip_address)


def new_idempotency_key() -> str:
    """Generate a fresh idempotence key for YooKassa API calls."""
    return str(uuid.uuid4())
