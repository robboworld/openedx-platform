# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
"""API of «Ответы учащегося» in the gradebook MFE (see answers.py)."""

from django.conf import settings
from django.urls import re_path

from .answers import LearnerAnswersView

app_name = 'robbo_gradebook'

urlpatterns = [
    re_path(
        fr'^api/robbo/v1/gradebook/{settings.COURSE_ID_PATTERN}/answers/?$',
        LearnerAnswersView.as_view(),
        name='learner_answers',
    ),
]
