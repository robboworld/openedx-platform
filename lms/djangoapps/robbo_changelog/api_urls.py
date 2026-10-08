# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (site changelog). See NOTICE at repository root.
"""
API of the «Что нового» header button. The LMS serves it to its pages and MFEs (``urls.py``);
Studio serves the same API to its own Mako pages, which cannot call the LMS cross-origin.
"""

from django.urls import path

from . import api

app_name = 'robbo_changelog'

urlpatterns = [
    path('api/robbo/v1/whats-new/status', api.status, name='api_status'),
    path('api/robbo/v1/whats-new/entries', api.panel, name='api_entries'),
    path('api/robbo/v1/whats-new/read', api.mark_read, name='api_read'),
    path('api/robbo/v1/whats-new/widget.js', api.widget, name='widget'),
]
