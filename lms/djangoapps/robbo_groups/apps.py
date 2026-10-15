# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (course groups). See NOTICE at repository root.

"""Application configuration for Robbo course groups."""

from django.apps import AppConfig


class RobboGroupsConfig(AppConfig):
    """Invite links that enroll a learner into a course and its group (cohort)."""

    name = 'lms.djangoapps.robbo_groups'
    label = 'robbo_groups'
    verbose_name = 'Robbo Course Groups'
    default_auto_field = 'django.db.models.AutoField'
