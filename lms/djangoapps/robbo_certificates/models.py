# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (certificate designs). See NOTICE at repository root.

"""
Certificate designs uploaded by platform staff (background image + positioned text fields),
and paid certificates: the price of a course's certificate and who has the right to it.
"""

import uuid

from django.contrib.auth import get_user_model
from django.db import models
from model_utils.models import TimeStampedModel
from opaque_keys.edx.django.models import CourseKeyField
from simple_history.models import HistoricalRecords

from openedx.core.djangoapps.course_groups.models import CourseUserGroup

User = get_user_model()


def generate_design_slug():
    """Design id as stored in course Advanced Settings; never clashes with theme partial names."""
    return f'custom-{uuid.uuid4().hex[:8]}'


def background_upload_path(instance, filename):
    extension = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'png'
    return f'robbo-certificate-designs/{instance.slug}-{uuid.uuid4().hex[:8]}.{extension}'


class CertificateDesign(TimeStampedModel):
    """
    A certificate sheet designed in Studio: an A4 landscape background and a list of fields
    (see fields.validate_fields for the schema). Rendered by
    robbo-theme/lms/templates/certificates/_robbo-design-uploaded.html.

    .. no_pii:
    """

    slug = models.SlugField(max_length=64, unique=True, default=generate_design_slug, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    background = models.FileField(upload_to=background_upload_path)
    fields = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    # Made by the Robbo dev team (shown as «Кастомный»), not by staff in the Studio builder
    # (shown as «Из конструктора»). Set in Django admin; editing in the builder keeps it.
    is_custom = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')

    class Meta:
        ordering = ('title',)

    def __str__(self):
        return f'{self.title} ({self.slug})'


def generate_certificate_sku():
    return f'ROBBO-CERT-{uuid.uuid4().hex[:8].upper()}'


def default_free_for_modes():
    return ['verified']


class CertificateOffer(TimeStampedModel):
    """
    A course run whose certificate is sold: without a CertificateEntitlement (or a free case, see
    offers.is_free_for) the certificate generation filter (filters.py) does not let it be created.
    Set by platform staff and superusers; see docs/paid-certificates.md in the meta repo.

    .. no_pii:
    """

    course_key = CourseKeyField(max_length=255, unique=True)
    is_enabled = models.BooleanField(default=True, db_index=True)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=8, default='RUB')
    # Percent of the course grade from which the certificate is given; empty = the course passing grade.
    # Never below the passing grade: the platform does not create a certificate for a failed course.
    min_percent = models.PositiveSmallIntegerField(null=True, blank=True)
    # Enrollment modes that get the certificate free (paid the course → the certificate is included)
    free_for_modes = models.JSONField(default=default_free_for_modes, blank=True)
    # Groups (cohorts) of the course that get the certificate free: B2B, B2G, partners
    free_for_cohorts = models.ManyToManyField(CourseUserGroup, blank=True, related_name='+')
    sku = models.CharField(max_length=64, unique=True, default=generate_certificate_sku, editable=False)
    updated_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')

    history = HistoricalRecords()

    class Meta:
        ordering = ('course_key',)

    def __str__(self):
        return f'{self.course_key}: {self.price} {self.currency}'


class CertificateEntitlement(TimeStampedModel):
    """
    The right of a learner to the certificate of a course with a CertificateOffer: bought or granted by staff.
    Kept when the price changes or the offer is turned off; a refund sets revoked_at instead of deleting the row.

    .. no_pii:
    """

    SOURCE_PAID = 'paid'
    SOURCE_STAFF_GRANT = 'staff_grant'
    SOURCE_CHOICES = (
        (SOURCE_PAID, 'Paid'),
        (SOURCE_STAFF_GRANT, 'Granted by staff'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='robbo_certificate_entitlements')
    course_key = CourseKeyField(max_length=255, db_index=True)
    source = models.CharField(max_length=16, choices=SOURCE_CHOICES)
    # robbo_payments.Order.order_number; not a ForeignKey: this app is also installed in Studio, robbo_payments is not
    order_number = models.CharField(max_length=32, blank=True, default='')
    granted_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = (('user', 'course_key'),)

    def __str__(self):
        return f'{self.user_id}:{self.course_key} ({self.source})'


class CertificateOfferNotice(TimeStampedModel):
    """
    The learner was told «Курс пройден — сертификат можно оформить за N ₽» (bell and email): once per
    learner and course, however many times the grade is recalculated and the command is run
    (notifications.py). Kept when the platform deletes old notifications.

    .. no_pii:
    """

    SOURCE_PASSED = 'passed'
    SOURCE_COMMAND = 'command'
    SOURCE_CHOICES = (
        (SOURCE_PASSED, 'Passed the course'),
        (SOURCE_COMMAND, 'robbo_certificate_offer_notify'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='+')
    course_key = CourseKeyField(max_length=255, db_index=True)
    source = models.CharField(max_length=16, choices=SOURCE_CHOICES)

    class Meta:
        unique_together = (('user', 'course_key'),)

    def __str__(self):
        return f'{self.user_id}:{self.course_key} ({self.source})'
