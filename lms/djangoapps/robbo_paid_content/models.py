# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (paid content). See NOTICE at repository root.
"""The paid content policy of a course run."""

from django.contrib.auth import get_user_model
from django.db import models
from model_utils.models import TimeStampedModel
from opaque_keys.edx.django.models import CourseKeyField
from simple_history.models import HistoricalRecords

User = get_user_model()


class PaidContentPolicy(TimeStampedModel):
    """
    What of the course is for learners with full access (the «verified» mode) only. The rules add up:
    sections and subsections marked «Только полный доступ» in Studio (the block field
    robbo_paid_only), every section after the first free_sections, every graded problem.

    display and grading say what a learner on the free path gets instead. Set in Studio,
    «Настройки → Тип курса»; docs/paid-content.md in the meta repo.

    .. no_pii:
    """

    DISPLAY_LOCKED = 'locked'   # title shown, content replaced by «available with full access» + upgrade button
    DISPLAY_HIDDEN = 'hidden'   # not shown at all
    DISPLAY_CHOICES = ((DISPLAY_LOCKED, 'Locked'), (DISPLAY_HIDDEN, 'Hidden'))

    GRADING_ZERO = 'zero'           # paid graded problems count, as not done
    GRADING_EXCLUDED = 'excluded'   # paid graded problems are left out of the free learner's grade
    GRADING_CHOICES = ((GRADING_ZERO, 'Counted as zero'), (GRADING_EXCLUDED, 'Excluded'))

    course_key = CourseKeyField(max_length=255, unique=True)
    is_enabled = models.BooleanField(default=False)
    # Sections 1..N are free, the rest are paid; None — no such rule
    free_sections = models.PositiveSmallIntegerField(null=True, blank=True)
    graded_paid = models.BooleanField(default=False)
    display = models.CharField(max_length=16, choices=DISPLAY_CHOICES, default=DISPLAY_LOCKED)
    grading = models.CharField(max_length=16, choices=GRADING_CHOICES, default=GRADING_ZERO)
    updated_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')

    history = HistoricalRecords()

    class Meta:
        ordering = ('course_key',)

    def __str__(self):
        return f'{self.course_key}: {"on" if self.is_enabled else "off"}'
