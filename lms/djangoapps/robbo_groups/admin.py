# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (course groups). See NOTICE at repository root.

"""Django admin for group invite links (look-up and switching a link off; issued in the instructor dashboard)."""

from django.contrib import admin

from .models import GroupInvite


@admin.register(GroupInvite)
class GroupInviteAdmin(admin.ModelAdmin):
    list_display = ('code', 'cohort', 'is_active', 'created_by', 'modified')
    list_editable = ('is_active',)
    list_filter = ('is_active',)
    list_select_related = ('cohort', 'created_by')
    search_fields = ('code', 'cohort__name', 'cohort__course_id')
    readonly_fields = ('cohort', 'code', 'created_by', 'created', 'modified')
