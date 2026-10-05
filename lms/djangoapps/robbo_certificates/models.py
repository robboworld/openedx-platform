# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (certificate designs). See NOTICE at repository root.

"""Certificate designs uploaded by platform staff (background image + positioned text fields)."""

import uuid

from django.contrib.auth import get_user_model
from django.db import models
from model_utils.models import TimeStampedModel

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
