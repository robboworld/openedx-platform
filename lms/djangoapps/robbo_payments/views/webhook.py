# Copyright (C) 2024-2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (YooKassa checkout). See NOTICE at repository root.

"""YooKassa webhook handler."""

import logging

from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from ipware import get_client_ip

from ..constants import OrderStatus, PaymentAttemptStatus
from ..models import Order, PaymentAttempt
from ..processors.yookassa import is_trusted_webhook_ip, parse_webhook_notification
from ..services.fulfillment import FulfillmentError, fulfill_verified_upgrade
from ..utils import payments_enabled

log = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def yookassa_webhook(request):
    """
    Receive YooKassa payment notifications.

    Always returns HTTP 200 for trusted, parseable events so YooKassa does not retry indefinitely.
    """
    if not payments_enabled():
        return HttpResponse(status=404)

    client_ip, _ = get_client_ip(request)
    if not is_trusted_webhook_ip(client_ip):
        log.warning('Rejected YooKassa webhook from untrusted IP: %s', client_ip)
        return HttpResponseBadRequest('Untrusted source')

    try:
        notification = parse_webhook_notification(request.body)
    except Exception:
        log.exception('Failed to parse YooKassa webhook payload')
        return HttpResponseBadRequest('Invalid payload')

    payment = notification.object
    payment_id = getattr(payment, 'id', None)
    metadata = getattr(payment, 'metadata', {}) or {}
    order_number = metadata.get('order_number')

    order = None
    if order_number:
        order = Order.objects.filter(order_number=order_number).first()
    if order is None and payment_id:
        order = Order.objects.filter(yookassa_payment_id=payment_id).first()

    if order is None:
        log.error('YooKassa webhook for unknown order payment_id=%s metadata=%s', payment_id, metadata)
        return HttpResponse(status=200)

    PaymentAttempt.objects.create(
        order=order,
        event_type=notification.event,
        status=PaymentAttemptStatus.RECEIVED,
        source_ip=client_ip,
        payload={'event': notification.event, 'payment_id': payment_id},
    )

    event = notification.event
    if event == 'payment.succeeded':
        try:
            fulfill_verified_upgrade(order)
            PaymentAttempt.objects.create(
                order=order,
                event_type=event,
                status=PaymentAttemptStatus.SUCCEEDED,
                source_ip=client_ip,
                payload={'payment_id': payment_id},
            )
        except FulfillmentError:
            log.exception('Fulfillment failed for order %s', order.order_number)
            PaymentAttempt.objects.create(
                order=order,
                event_type=event,
                status=PaymentAttemptStatus.ERROR,
                source_ip=client_ip,
                payload={'payment_id': payment_id},
            )
    elif event == 'payment.canceled':
        if order.status == OrderStatus.PENDING:
            order.status = OrderStatus.CANCELED
            order.save(update_fields=['status', 'updated_at'])
        PaymentAttempt.objects.create(
            order=order,
            event_type=event,
            status=PaymentAttemptStatus.CANCELED,
            source_ip=client_ip,
            payload={'payment_id': payment_id},
        )

    return HttpResponse(status=200)
