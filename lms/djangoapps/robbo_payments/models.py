# Copyright (C) 2024-2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (YooKassa checkout). See NOTICE at repository root.

"""Commerce order models for Robbo YooKassa checkout."""

import uuid

from django.contrib.auth import get_user_model
from django.db import models
from opaque_keys.edx.django.models import CourseKeyField

from .constants import OrderStatus, PaymentAttemptStatus

User = get_user_model()


def generate_order_number():
    """Return a human-readable unique order number."""
    return f'ROBBO-{uuid.uuid4().hex[:12].upper()}'


class Order(models.Model):
    """
    A checkout order for a verified course upgrade.

    .. no_pii:
    """

    order_number = models.CharField(max_length=32, unique=True, default=generate_order_number, db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='robbo_payment_orders')
    course_key = CourseKeyField(max_length=255, db_index=True)
    sku = models.CharField(max_length=255, db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=8, default='RUB')
    status = models.CharField(
        max_length=16,
        choices=OrderStatus.CHOICES,
        default=OrderStatus.PENDING,
        db_index=True,
    )
    idempotency_key = models.CharField(max_length=64, unique=True)
    yookassa_payment_id = models.CharField(max_length=64, blank=True, null=True, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        app_label = 'robbo_payments'
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=['user', 'course_key', 'status']),
        ]

    def __str__(self):
        return self.order_number


class PaymentAttempt(models.Model):
    """
    Audit log for YooKassa webhook and API interactions.

    .. no_pii:
    """

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='payment_attempts')
    event_type = models.CharField(max_length=64, blank=True, default='')
    status = models.CharField(max_length=16, choices=PaymentAttemptStatus.CHOICES, default=PaymentAttemptStatus.RECEIVED)
    source_ip = models.GenericIPAddressField(blank=True, null=True)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'robbo_payments'
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.order.order_number}:{self.event_type}'
