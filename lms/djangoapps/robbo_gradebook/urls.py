# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
"""API of «Ответы учащегося» (answers.py) and of the PDF report (progress.py) in the gradebook MFE."""

from django.conf import settings
from django.urls import re_path

from .answers import LearnerAnswersView
from .progress import CourseLearnersView, LearnerProgressView

app_name = 'robbo_gradebook'

urlpatterns = [
    re_path(
        fr'^api/robbo/v1/gradebook/{settings.COURSE_ID_PATTERN}/answers/?$',
        LearnerAnswersView.as_view(),
        name='learner_answers',
    ),
    re_path(
        fr'^api/robbo/v1/gradebook/{settings.COURSE_ID_PATTERN}/learners/?$',
        CourseLearnersView.as_view(),
        name='course_learners',
    ),
    re_path(
        fr'^api/robbo/v1/gradebook/{settings.COURSE_ID_PATTERN}/progress/?$',
        LearnerProgressView.as_view(),
        name='learner_progress',
    ),
]
