# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (certificate designs). See NOTICE at repository root.

"""Django admin for certificate designs (mainly the «Кастомный» flag) and paid certificates."""

from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from simple_history.admin import SimpleHistoryAdmin

from openedx.core.djangoapps.content.course_overviews.models import CourseOverview

from .models import CertificateDesign, CertificateEntitlement, CertificateOffer, CertificateOfferNotice
from .offers import min_percent_error


@admin.register(CertificateDesign)
class CertificateDesignAdmin(admin.ModelAdmin):
    """Builder designs are edited in Studio; here: custom designs, the custom flag, restoring deleted ones."""

    list_display = ('title', 'slug', 'is_custom', 'is_active', 'created_by', 'modified')
    list_editable = ('is_custom', 'is_active')
    list_filter = ('is_custom', 'is_active')
    search_fields = ('title', 'slug')
    readonly_fields = ('slug', 'created_by', 'created', 'modified')


class CertificateOfferForm(forms.ModelForm):
    """Price above zero, threshold not below the course passing grade, groups of this course only."""

    class Meta:
        model = CertificateOffer
        fields = ('course_key', 'is_enabled', 'price', 'min_percent', 'free_for_modes', 'free_for_cohorts')

    def clean_price(self):
        price = self.cleaned_data['price']
        if price is None or price <= 0:
            raise ValidationError('Цена должна быть больше нуля.')
        return price

    def clean_free_for_modes(self):
        modes = self.cleaned_data.get('free_for_modes') or []
        if not isinstance(modes, list) or not all(isinstance(mode, str) for mode in modes):
            raise ValidationError('Список режимов записи, например ["verified"].')
        return modes

    def clean(self):
        cleaned = super().clean()
        course_key = cleaned.get('course_key')
        if course_key is None:
            return cleaned
        if isinstance(course_key, str):
            try:
                course_key = CourseKey.from_string(course_key.strip())
            except InvalidKeyError:
                self.add_error('course_key', 'Ключ курса вида course-v1:ORG+NUM+RUN.')
                return cleaned
            cleaned['course_key'] = course_key
        if not CourseOverview.course_exists(course_key):
            self.add_error('course_key', 'Такого курса нет.')
            return cleaned
        min_percent_message = min_percent_error(course_key, cleaned.get('min_percent'))
        if min_percent_message:
            self.add_error('min_percent', min_percent_message)
        cohorts = cleaned.get('free_for_cohorts')
        if cohorts and any(cohort.course_id != course_key for cohort in cohorts):
            self.add_error('free_for_cohorts', 'Можно выбрать только группы этого курса.')
        return cleaned


@admin.register(CertificateOffer)
class CertificateOfferAdmin(SimpleHistoryAdmin):
    """Paid certificate of a course: price, threshold, who gets it free. History: «История» button."""

    form = CertificateOfferForm
    list_display = ('course_key', 'is_enabled', 'price', 'currency', 'min_percent', 'sku', 'updated_by', 'modified')
    list_filter = ('is_enabled',)
    search_fields = ('course_key', 'sku')
    readonly_fields = ('sku', 'currency', 'updated_by', 'created', 'modified')
    filter_horizontal = ('free_for_cohorts',)

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(CertificateEntitlement)
class CertificateEntitlementAdmin(admin.ModelAdmin):
    """Who has the right to a paid certificate; a refund sets «revoked at» instead of deleting."""

    list_display = ('user', 'course_key', 'source', 'order_number', 'granted_by', 'revoked_at', 'created')
    list_filter = ('source', 'revoked_at')
    search_fields = ('user__username', 'user__email', 'course_key', 'order_number')
    raw_id_fields = ('user', 'granted_by')
    readonly_fields = ('order_number', 'created', 'modified')


@admin.register(CertificateOfferNotice)
class CertificateOfferNoticeAdmin(admin.ModelAdmin):
    """Who was told the certificate can be bought; deleting a row lets the notification go out once more."""

    list_display = ('user', 'course_key', 'source', 'created')
    list_filter = ('source',)
    search_fields = ('user__username', 'user__email', 'course_key')
    raw_id_fields = ('user',)
    readonly_fields = ('user', 'course_key', 'source', 'created', 'modified')
