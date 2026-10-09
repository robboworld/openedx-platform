# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (site changelog). See NOTICE at repository root.

from django.urls import re_path

from . import api_urls
from .views import whats_new

app_name = 'robbo_changelog'

urlpatterns = [
    re_path(r'^whats-new/?$', whats_new, name='whats_new'),
    *api_urls.urlpatterns,
]
