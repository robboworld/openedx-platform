# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (course groups). See NOTICE at repository root.

"""Invite links of course groups (Open edX cohorts)."""

import secrets

from django.contrib.auth import get_user_model
from django.db import models
from model_utils.models import TimeStampedModel

from openedx.core.djangoapps.course_groups.models import CourseUserGroup

User = get_user_model()

# No 0/o, 1/l/i: a teacher may read the link aloud or copy it from a projector.
INVITE_CODE_ALPHABET = 'abcdefghjkmnpqrstuvwxyz23456789'
INVITE_CODE_LENGTH = 10


def generate_invite_code():
    return ''.join(secrets.choice(INVITE_CODE_ALPHABET) for _ in range(INVITE_CODE_LENGTH))


class GroupInvite(TimeStampedModel):
    """
    The invite link of one course group: /join/<code> enrolls the learner in the course and adds
    them to the group. One link per group; a new code replaces the old one, which stops working.

    .. no_pii:
    """

    cohort = models.OneToOneField(CourseUserGroup, on_delete=models.CASCADE, related_name='robbo_invite')
    code = models.CharField(max_length=32, unique=True, default=generate_invite_code)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')

    def __str__(self):
        return f'{self.cohort.course_id} / {self.cohort.name} ({self.code})'
