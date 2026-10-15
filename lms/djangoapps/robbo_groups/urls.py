# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (course groups). See NOTICE at repository root.

"""URLs of group invite links."""

from django.conf import settings
from django.urls import path, re_path

from . import views

app_name = 'robbo_groups'

urlpatterns = [
    path('join/<str:code>', views.join, name='join'),
    # Next to the stock cohort URLs (/courses/<id>/cohorts/<cohort_id>/add) used by the same editor.
    re_path(
        fr'^courses/{settings.COURSE_ID_PATTERN}/cohorts/(?P<cohort_id>[0-9]+)/robbo-invite$',
        views.cohort_invite, name='cohort_invite',
    ),
    re_path(
        fr'^courses/{settings.COURSE_ID_PATTERN}/cohorts/(?P<cohort_id>[0-9]+)/robbo-members$',
        views.cohort_members, name='cohort_members',
    ),
    re_path(
        fr'^courses/{settings.COURSE_ID_PATTERN}/cohorts/(?P<cohort_id>[0-9]+)/robbo-delete$',
        views.cohort_delete, name='cohort_delete',
    ),
]
