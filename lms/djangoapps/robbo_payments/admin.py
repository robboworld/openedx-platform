# Copyright (C) 2024-2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (YooKassa checkout). See NOTICE at repository root.

"""Django admin for Robbo payments."""

from django.contrib import admin

from .models import Order, PaymentAttempt


class PaymentAttemptInline(admin.TabularInline):
    model = PaymentAttempt
    extra = 0
    readonly_fields = ('event_type', 'status', 'source_ip', 'payload', 'created_at')
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'order_number',
        'user',
        'course_key',
        'amount',
        'currency',
        'status',
        'created_at',
        'paid_at',
    )
    list_filter = ('status', 'currency', 'created_at')
    search_fields = ('order_number', 'user__username', 'user__email', 'sku', 'yookassa_payment_id')
    readonly_fields = (
        'order_number',
        'user',
        'course_key',
        'sku',
        'amount',
        'currency',
        'idempotency_key',
        'yookassa_payment_id',
        'created_at',
        'updated_at',
        'paid_at',
    )
    inlines = (PaymentAttemptInline,)


@admin.register(PaymentAttempt)
class PaymentAttemptAdmin(admin.ModelAdmin):
    list_display = ('order', 'event_type', 'status', 'source_ip', 'created_at')
    list_filter = ('status', 'event_type', 'created_at')
    search_fields = ('order__order_number', 'event_type')
    readonly_fields = ('order', 'event_type', 'status', 'source_ip', 'payload', 'created_at')
