# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (human-readable errors). See NOTICE at repository root.
"""URLs of the error journal: browser reports (API) and the support page."""

from django.urls import path

from . import views

app_name = 'robbo_errors'

urlpatterns = [
    path('api/robbo/v1/errors/report', views.report, name='report'),
    path('robbo/errors/', views.lookup, name='lookup'),
    path('robbo/errors/<int:pk>/', views.incident, name='incident'),
]
