# Copyright (C) 2024-2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (YooKassa checkout). See NOTICE at repository root.

"""Post-payment enrollment fulfillment."""

import logging

from django.db import transaction
from django.utils import timezone

from common.djangoapps.course_modes.models import CourseMode
from common.djangoapps.student.models import CourseEnrollment

from ..constants import OrderStatus
from ..models import Order

log = logging.getLogger(__name__)


class FulfillmentError(Exception):
    """Enrollment could not be upgraded after payment."""


@transaction.atomic
def fulfill_verified_upgrade(order: Order) -> Order:
    """
    Upgrade the user's enrollment to verified after successful payment.

    Idempotent: already-paid orders or already-verified enrollments succeed without error.
    """
    order = Order.objects.select_for_update().get(pk=order.pk)

    if order.status == OrderStatus.PAID:
        return order

    if order.status != OrderStatus.PENDING:
        raise FulfillmentError(f'Order {order.order_number} is in status {order.status}, cannot fulfill')

    enrollment = CourseEnrollment.get_enrollment(order.user, order.course_key)
    if enrollment is None:
        raise FulfillmentError(
            f'User {order.user.id} is not enrolled in {order.course_key} for order {order.order_number}'
        )

    if enrollment.mode == CourseMode.VERIFIED:
        log.info(
            'Order %s: user %s already verified in %s; marking paid',
            order.order_number,
            order.user.id,
            order.course_key,
        )
    elif enrollment.mode in (CourseMode.AUDIT, CourseMode.HONOR):
        previous_mode = enrollment.mode
        enrollment.update_enrollment(mode=CourseMode.VERIFIED)
        log.info(
            'Order %s: upgraded user %s from %s to verified in %s',
            order.order_number,
            order.user.id,
            previous_mode,
            order.course_key,
        )
    else:
        raise FulfillmentError(
            f'Unsupported enrollment mode {enrollment.mode!r} for order {order.order_number}'
        )

    order.status = OrderStatus.PAID
    order.paid_at = timezone.now()
    order.save(update_fields=['status', 'paid_at', 'updated_at'])
    return order
