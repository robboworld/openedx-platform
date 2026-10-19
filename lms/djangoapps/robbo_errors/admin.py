# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (human-readable errors). See NOTICE at repository root.
"""
Django admin of the error journal, read-only, for developers with admin access. Support staff use
the support page (views.lookup): admin needs is_staff, which in Open edX means staff of every course.
"""

from django.contrib import admin

from .models import ErrorIncident


@admin.register(ErrorIncident)
class ErrorIncidentAdmin(admin.ModelAdmin):
    list_display = ('short_id', 'code', 'status', 'source', 'site', 'path', 'user', 'count', 'last_seen')
    list_filter = ('code', 'source', 'site', 'audience')
    list_select_related = ('user',)
    search_fields = ('incident_id', 'merged_ids', 'code', 'user__username', 'path')
    date_hierarchy = 'last_seen'
    raw_id_fields = ('user',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
