# Copyright (C) 2024-2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (YooKassa checkout). See NOTICE at repository root.

"""Shared helpers for Robbo payments views."""

from django.conf import settings

from lms.djangoapps.commerce.models import CommerceConfiguration


def payments_enabled() -> bool:
    """True when Robbo payments and commerce checkout are both enabled."""
    if not getattr(settings, 'ROBBO_PAYMENTS_ENABLED', False):
        return False
    config = CommerceConfiguration.current()
    return config.enabled and config.checkout_on_ecommerce_service


def format_checkout_price_display(amount, currency):
    """
    Human-readable price for checkout CTA (RUB → «100 ₽»).

    Modifications Copyright (C) 2024-2026 Robbo. See NOTICE at repository root.
    """
    code = (currency or '').upper()
    if code == 'RUB':
        numeric = amount
        if numeric == int(numeric):
            numeric = int(numeric)
        return f'{numeric} ₽'
    return f'{amount} {code}'
