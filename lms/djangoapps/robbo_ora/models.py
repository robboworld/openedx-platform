# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only

"""Models of the Robbo ORA app."""

from django.contrib.auth import get_user_model
from django.db import models
from model_utils.models import TimeStampedModel
from opaque_keys.edx.django.models import CourseKeyField

User = get_user_model()


class OraRetakeGrant(TimeStampedModel):
    """
    The grader ticked «Разрешить пересдачу» for this graded submission. Lives until the learner
    starts the retake: the new submission has no grant, so one tick is one attempt
    (cms/djangoapps/contentstore/robbo_ora_retake.py).

    .. no_pii:
    """

    submission_uuid = models.CharField(max_length=128, unique=True)
    course_id = CourseKeyField(max_length=255, db_index=True)
    granted_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name='+')

    def __str__(self):
        return f'{self.course_id}: {self.submission_uuid}'
