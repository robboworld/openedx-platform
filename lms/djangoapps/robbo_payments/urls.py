# Copyright (C) 2024-2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (YooKassa checkout). See NOTICE at repository root.

"""URL routes for Robbo YooKassa payments."""

from django.urls import path

from .views.checkout import basket_add
from .views.receipt import receipt
from .views.webhook import yookassa_webhook

app_name = 'robbo_payments'

urlpatterns = [
    path('basket/add/', basket_add, name='basket_add'),
    path('checkout/receipt/', receipt, name='receipt'),
    path('payments/yookassa/webhook/', yookassa_webhook, name='yookassa_webhook'),
]
