# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution. See NOTICE at repository root.

from django.urls import path

from . import api, service_api, views

app_name = 'robbo_notifications'

urlpatterns = [
    path('api/robbo/v1/notifications/widget.js', views.widget, name='widget'),
    path('api/robbo/v1/notifications/courses/', api.CoursesView.as_view(), name='courses'),
    path('api/robbo/v1/notifications/read-all/', api.ReadAllView.as_view(), name='read_all'),
    path('api/robbo/v1/notifications/disable-all/', api.DisableAllView.as_view(), name='disable_all'),
    path('api/robbo/v1/notifications/account-settings/', api.AccountSettingsView.as_view(), name='account_settings'),
    path('api/robbo/v1/notifications/courses/reset/', api.ResetCoursesView.as_view(), name='courses_reset'),
    path('api/robbo/v1/notifications/learners/', api.CourseLearnersView.as_view(), name='course_learners'),
    # The LK server (service_api.py).
    path('api/robbo/v1/notifications/service/feed/', service_api.FeedView.as_view(), name='service_feed'),
    path('api/robbo/v1/notifications/service/unread-count/', service_api.UnreadCountView.as_view(),
         name='service_unread_count'),
    path('api/robbo/v1/notifications/service/read/', service_api.ReadView.as_view(), name='service_read'),
]
