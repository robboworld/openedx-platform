# Copyright (C) 2024-2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Tutor plugin: Robbo YooKassa payments (LMS-native checkout).

"""Tutor plugin for Robbo YooKassa commerce."""

from __future__ import annotations

from tutor import hooks

_PATCH_PAYMENTS_DEV = """
ROBBO_PAYMENTS_ENABLED = True
YOOKASSA_SHOP_ID = "{{ YOOKASSA_SHOP_ID }}"
YOOKASSA_SECRET_KEY = "{{ YOOKASSA_SECRET_KEY }}"
ROBBO_PAYMENTS_DEFAULT_CURRENCY = "{{ ROBBO_PAYMENTS_DEFAULT_CURRENCY }}"
ROBBO_PAYMENTS_SEND_RECEIPT = {{ ROBBO_PAYMENTS_SEND_RECEIPT }}
ROBBO_PAYMENTS_RECEIPT_VAT_CODE = {{ ROBBO_PAYMENTS_RECEIPT_VAT_CODE }}
ROBBO_PAYMENTS_RECEIPT_PAYMENT_SUBJECT = "{{ ROBBO_PAYMENTS_RECEIPT_PAYMENT_SUBJECT }}"
ROBBO_PAYMENTS_RECEIPT_PAYMENT_MODE = "{{ ROBBO_PAYMENTS_RECEIPT_PAYMENT_MODE }}"
ECOMMERCE_PUBLIC_URL_ROOT = "http://{{ LMS_HOST }}:8000"
"""

_PATCH_PAYMENTS_PROD = """
ROBBO_PAYMENTS_ENABLED = True
YOOKASSA_SHOP_ID = "{{ YOOKASSA_SHOP_ID }}"
YOOKASSA_SECRET_KEY = "{{ YOOKASSA_SECRET_KEY }}"
ROBBO_PAYMENTS_DEFAULT_CURRENCY = "{{ ROBBO_PAYMENTS_DEFAULT_CURRENCY }}"
ROBBO_PAYMENTS_SEND_RECEIPT = {{ ROBBO_PAYMENTS_SEND_RECEIPT }}
ROBBO_PAYMENTS_RECEIPT_VAT_CODE = {{ ROBBO_PAYMENTS_RECEIPT_VAT_CODE }}
ROBBO_PAYMENTS_RECEIPT_PAYMENT_SUBJECT = "{{ ROBBO_PAYMENTS_RECEIPT_PAYMENT_SUBJECT }}"
ROBBO_PAYMENTS_RECEIPT_PAYMENT_MODE = "{{ ROBBO_PAYMENTS_RECEIPT_PAYMENT_MODE }}"
ECOMMERCE_PUBLIC_URL_ROOT = "{% if ENABLE_HTTPS %}https{% else %}http{% endif %}://{{ LMS_HOST }}"
"""

_PATCH_YOOKASSA_PIP = """
RUN --mount=type=cache,target=/openedx/.cache/pip,sharing=shared \\
    pip install 'yookassa>=3.0.0'
"""

hooks.Filters.CONFIG_DEFAULTS.add_items(
    [
        ("YOOKASSA_SHOP_ID", ""),
        ("YOOKASSA_SECRET_KEY", ""),
        ("ROBBO_PAYMENTS_DEFAULT_CURRENCY", "RUB"),
        ("ROBBO_PAYMENTS_SEND_RECEIPT", True),
        ("ROBBO_PAYMENTS_RECEIPT_VAT_CODE", 1),
        ("ROBBO_PAYMENTS_RECEIPT_PAYMENT_SUBJECT", "service"),
        ("ROBBO_PAYMENTS_RECEIPT_PAYMENT_MODE", "full_payment"),
    ]
)

hooks.Filters.CONFIG_UNIQUE.add_items(
    [
        ("YOOKASSA_SHOP_ID", ""),
        ("YOOKASSA_SECRET_KEY", ""),
    ]
)

hooks.Filters.ENV_PATCHES.add_items(
    [
        ("openedx-lms-development-settings", _PATCH_PAYMENTS_DEV),
        ("openedx-lms-production-settings", _PATCH_PAYMENTS_PROD),
        ("openedx-dockerfile-post-python-requirements", _PATCH_YOOKASSA_PIP),
    ]
)
