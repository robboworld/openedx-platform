# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
"""API of «Проверка по учащимся» in the ORA grading MFE (see learner_grading.py)."""

from django.conf import settings
from django.urls import re_path

from .learner_grading import CourseLearnersView, LearnerAnswersView

app_name = 'robbo_ora'

urlpatterns = [
    re_path(
        fr'^api/robbo/v1/ora-grading/{settings.COURSE_ID_PATTERN}/learners/(?P<username>[^/]+)/?$',
        LearnerAnswersView.as_view(),
        name='learner_answers',
    ),
    re_path(
        fr'^api/robbo/v1/ora-grading/{settings.COURSE_ID_PATTERN}/?$',
        CourseLearnersView.as_view(),
        name='course_learners',
    ),
]
