# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution. See NOTICE at repository root.
"""
The header bell on Studio's own Mako pages, as «Что нового» (robbo_changelog/api_urls.py): those
pages cannot call the LMS cross-origin, so Studio serves the widget and what it calls on the Studio
session — the stock list / count / seen / read endpoints and «Прочитать все». The authoring MFE
lives on the LMS host and uses the LMS API (urls.py).
"""
from django.urls import path

from openedx.core.djangoapps.notifications.views import (
    MarkNotificationsSeenAPIView,
    NotificationCountView,
    NotificationListAPIView,
    NotificationReadAPIView,
)

from . import api, views

app_name = 'robbo_notifications'

urlpatterns = [
    path('api/robbo/v1/notifications/widget.js', views.widget, name='widget'),
    path('api/robbo/v1/notifications/read-all/', api.ReadAllView.as_view(), name='read_all'),
    path('api/notifications/', NotificationListAPIView.as_view(), name='notifications-list'),
    path('api/notifications/count/', NotificationCountView.as_view(), name='notifications-count'),
    path('api/notifications/mark-seen/<app_name>/', MarkNotificationsSeenAPIView.as_view(),
         name='mark-notifications-seen'),
    path('api/notifications/read/', NotificationReadAPIView.as_view(), name='notifications-read'),
]
