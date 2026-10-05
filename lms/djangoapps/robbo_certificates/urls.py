# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (certificate designs). See NOTICE at repository root.
"""URLs for the instructor dashboard certificate fixes."""

from django.conf import settings
from django.urls import re_path

from . import views

app_name = 'robbo_certificates'

urlpatterns = [
    re_path(
        fr'^courses/{settings.COURSE_ID_PATTERN}/instructor/robbo-certificates/add-honor-mode$',
        views.add_honor_mode, name='add_honor_mode',
    ),
    re_path(
        fr'^courses/{settings.COURSE_ID_PATTERN}/instructor/robbo-certificates/remove-audit-mode$',
        views.remove_audit_mode, name='remove_audit_mode',
    ),
    re_path(
        fr'^courses/{settings.COURSE_ID_PATTERN}/instructor/robbo-certificates/enrollments-to-honor$',
        views.enrollments_to_honor, name='enrollments_to_honor',
    ),
    re_path(
        fr'^courses/{settings.COURSE_ID_PATTERN}/instructor/robbo-certificates/enable-self-generation$',
        views.enable_self_generation, name='enable_self_generation',
    ),
    re_path(
        fr'^courses/{settings.COURSE_ID_PATTERN}/instructor/robbo-certificates/repair-display-behavior$',
        views.repair_display_behavior, name='repair_display_behavior',
    ),
]
