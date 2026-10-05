# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (certificate designs). See NOTICE at repository root.

"""Django admin for certificate designs (mainly the «Кастомный» flag)."""

from django.contrib import admin

from .models import CertificateDesign


@admin.register(CertificateDesign)
class CertificateDesignAdmin(admin.ModelAdmin):
    """Builder designs are edited in Studio; here: custom designs, the custom flag, restoring deleted ones."""

    list_display = ('title', 'slug', 'is_custom', 'is_active', 'created_by', 'modified')
    list_editable = ('is_custom', 'is_active')
    list_filter = ('is_custom', 'is_active')
    search_fields = ('title', 'slug')
    readonly_fields = ('slug', 'created_by', 'created', 'modified')
