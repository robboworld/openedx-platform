# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only

from django.urls import path

from .views import lk_handoff, lk_portal

app_name = 'robbo_lk_handoff'

urlpatterns = [
    path('robbo/lk-handoff', lk_handoff, name='lk_handoff'),
    path('robbo/lk', lk_portal, name='lk_portal'),
]
