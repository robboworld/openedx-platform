# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (human-readable errors). See NOTICE at repository root.
"""The error journal: what support finds by the code a user sends them."""

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

from .ids import short_id

User = get_user_model()


class ErrorIncident(models.Model):
    """
    One error a user saw, or one per-day counter of a code (``catalog.yaml`` ``journal: count``).

    Repeats of the same error by the same user on the same path within a minute are merged into one
    row (``count``, ``merged_ids``), so a page retrying in a loop cannot flood the table. Rows older
    than ``ROBBO_ERRORS_RETENTION_DAYS`` are purged as new ones are written.

    .. pii: The user who saw the error and the path of the request; no names, emails or request bodies.
        A traceback of a server error may quote values the code was working with.
    .. pii_types: id, other
    .. pii_retirement: retained
    """

    # Hex of the request UUID Caddy assigns (X-Request-ID), without dashes; users see the first 8.
    incident_id = models.CharField(max_length=32, db_index=True, blank=True)
    # First 8 hex of later occurrences merged into this row, space-separated: their numbers are searchable too.
    merged_ids = models.TextField(blank=True, default='')
    code = models.CharField(max_length=64, db_index=True)
    status = models.PositiveSmallIntegerField(null=True, blank=True)
    # Host of the request, e.g. online.robbo.ru or studio.online.robbo.ru.
    site = models.CharField(max_length=255, blank=True)
    # lms, cms, or what the browser reported: mfe:learning, mfe:authoring…
    source = models.CharField(max_length=64)
    method = models.CharField(max_length=10, blank=True)
    # Path of the failed request, without the query string.
    path = models.CharField(max_length=512, blank=True)
    # Page the user was on (browser reports), without the query string.
    page = models.CharField(max_length=512, blank=True)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    # learner or staff: whom the message told to turn to a teacher or to support.
    audience = models.CharField(max_length=16, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    developer_message = models.TextField(blank=True)
    traceback = models.TextField(blank=True)
    count = models.PositiveIntegerField(default=1)
    first_seen = models.DateTimeField(default=timezone.now, db_index=True)
    last_seen = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        verbose_name = 'error incident'
        ordering = ('-last_seen',)

    def __str__(self):
        return f'{self.code} · {self.short_id or "—"}'

    @property
    def short_id(self):
        """``7F3A-29C1``: how the number is shown to the user."""
        return short_id(self.incident_id)
