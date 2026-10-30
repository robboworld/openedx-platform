# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (paid content). See NOTICE at repository root.
"""Paid content: what learners on the free path can't open without full access."""

from django.apps import AppConfig


class RobboPaidContentConfig(AppConfig):
    name = 'lms.djangoapps.robbo_paid_content'
    verbose_name = 'Robbo Paid Content'
    default_auto_field = 'django.db.models.AutoField'
