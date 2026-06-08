# Copyright (C) 2024-2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (YooKassa checkout). See NOTICE at repository root.

"""Application configuration for Robbo payments."""

from django.apps import AppConfig


class RobboPaymentsConfig(AppConfig):
    """Django app config for Robbo YooKassa payments."""

    name = 'lms.djangoapps.robbo_payments'
    verbose_name = 'Robbo Payments'
