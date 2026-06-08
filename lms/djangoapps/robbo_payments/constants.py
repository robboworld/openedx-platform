# Copyright (C) 2024-2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (YooKassa checkout). See NOTICE at repository root.

"""Constants for Robbo payments."""


class OrderStatus:
    """Order lifecycle states."""

    PENDING = 'pending'
    PAID = 'paid'
    FAILED = 'failed'
    CANCELED = 'canceled'
    REFUNDED = 'refunded'

    CHOICES = (
        (PENDING, 'Pending'),
        (PAID, 'Paid'),
        (FAILED, 'Failed'),
        (CANCELED, 'Canceled'),
        (REFUNDED, 'Refunded'),
    )


class PaymentAttemptStatus:
    """Webhook / payment attempt outcomes."""

    RECEIVED = 'received'
    SUCCEEDED = 'succeeded'
    CANCELED = 'canceled'
    ERROR = 'error'

    CHOICES = (
        (RECEIVED, 'Received'),
        (SUCCEEDED, 'Succeeded'),
        (CANCELED, 'Canceled'),
        (ERROR, 'Error'),
    )
