# Copyright (C) 2024-2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (YooKassa checkout). See NOTICE at repository root.

"""Sync local order state with YooKassa when webhooks are delayed or unavailable."""

import logging

from ..constants import OrderStatus, PaymentAttemptStatus
from ..models import Order, PaymentAttempt
from ..processors.yookassa import YooKassaNotConfigured, YooKassaPaymentError, get_payment
from .fulfillment import FulfillmentError, fulfill_verified_upgrade

log = logging.getLogger(__name__)


def sync_order_from_yookassa(order: Order, *, source_ip=None) -> Order:
    """
    Refresh order status from YooKassa API.

    Used on the receipt page when webhooks cannot reach the LMS (common in local dev).
    Idempotent for paid orders.
    """
    order = Order.objects.get(pk=order.pk)
    if order.status != OrderStatus.PENDING:
        return order

    if not order.yookassa_payment_id:
        return order

    try:
        payment = get_payment(order.yookassa_payment_id)
    except (YooKassaNotConfigured, YooKassaPaymentError):
        log.exception('Failed to fetch YooKassa payment for order %s', order.order_number)
        return order

    payment_status = getattr(payment, 'status', None)
    if payment_status == 'succeeded':
        PaymentAttempt.objects.create(
            order=order,
            event_type='payment.succeeded',
            status=PaymentAttemptStatus.RECEIVED,
            source_ip=source_ip,
            payload={'payment_id': order.yookassa_payment_id, 'source': 'receipt_sync'},
        )
        try:
            order = fulfill_verified_upgrade(order)
            PaymentAttempt.objects.create(
                order=order,
                event_type='payment.succeeded',
                status=PaymentAttemptStatus.SUCCEEDED,
                source_ip=source_ip,
                payload={'payment_id': order.yookassa_payment_id, 'source': 'receipt_sync'},
            )
        except FulfillmentError:
            log.exception('Fulfillment failed during receipt sync for order %s', order.order_number)
            PaymentAttempt.objects.create(
                order=order,
                event_type='payment.succeeded',
                status=PaymentAttemptStatus.ERROR,
                source_ip=source_ip,
                payload={'payment_id': order.yookassa_payment_id, 'source': 'receipt_sync'},
            )
    elif payment_status == 'canceled':
        order.status = OrderStatus.CANCELED
        order.save(update_fields=['status', 'updated_at'])
        PaymentAttempt.objects.create(
            order=order,
            event_type='payment.canceled',
            status=PaymentAttemptStatus.CANCELED,
            source_ip=source_ip,
            payload={'payment_id': order.yookassa_payment_id, 'source': 'receipt_sync'},
        )

    return order
