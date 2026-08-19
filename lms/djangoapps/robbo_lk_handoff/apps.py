# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only

"""App config for LK → LMS session handoff."""

from django.apps import AppConfig


class RobboLkHandoffConfig(AppConfig):
    name = 'lms.djangoapps.robbo_lk_handoff'
    label = 'robbo_lk_handoff'
    verbose_name = 'Robbo LK → LMS session handoff'
