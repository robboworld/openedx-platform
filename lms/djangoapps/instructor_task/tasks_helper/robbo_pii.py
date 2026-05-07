# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution. See NOTICE at repository root.

"""
Robbo extended learner profile CSV for the instructor dashboard.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from time import time
from typing import Dict, FrozenSet, Iterable, List, Set

from django.conf import settings
from pytz import UTC
from xmodule.modulestore.django import modulestore

from common.djangoapps.student.models import CourseEnrollment
from lms.djangoapps.courseware.robbo_catalog import get_robbo_catalog_stubs
from lms.djangoapps.grades.course_grade_factory import CourseGradeFactory
from lms.djangoapps.instructor_analytics.basic import enrolled_students_features
from openedx.core.lib.courses import get_course_by_id

from .runner import TaskProgress
from .utils import upload_csv_to_report_store

TASK_LOG = logging.getLogger('edx.celery.task')

_INTEREST_META_KEY = 'robbo_course_interest_titles'
_MAX_GRADED_TESTS = 5
# Profile columns moved to the far right of the Robbo CSV (after interest_*).
_TAIL_PROFILE_FEATURES: FrozenSet[str] = frozenset({
    'language',
    'location',
    'gender',
    'level_of_education',
    'mailing_address',
    'goals',
    'enrollment_mode',
    'country',
})
_USER_ID_RE = re.compile(r'user_id=(\d+)')
_TITLE_RE = re.compile(r"course_title='((?:\\'|[^'])*)'")


def _profile_meta(profile) -> Dict[str, object]:
    if profile is None or not getattr(profile, 'meta', ''):
        return {}
    try:
        meta = json.loads(profile.meta)
    except (TypeError, ValueError):
        return {}
    return meta if isinstance(meta, dict) else {}


def _company_from_profile(profile) -> str:
    value = _profile_meta(profile).get('company')
    return '' if value is None else str(value)


def _interest_titles_from_profile(profile) -> Set[str]:
    raw_titles = _profile_meta(profile).get(_INTEREST_META_KEY)
    if not isinstance(raw_titles, list):
        return set()
    return {str(title).strip() for title in raw_titles if title}


def _interest_log_paths() -> List[str]:
    configured = getattr(settings, 'ROBBO_COURSE_INTEREST_LOG_PATHS', [])
    if isinstance(configured, str):
        configured = [configured]
    if not isinstance(configured, (list, tuple)):
        return []
    return [path for path in configured if path and os.path.isfile(path)]


def _interest_titles_from_logs() -> Dict[int, Set[str]]:
    by_user: Dict[int, Set[str]] = {}
    for path in _interest_log_paths():
        try:
            with open(path, encoding='utf-8', errors='replace') as log_file:
                for line in log_file:
                    if 'course_interest submitted' not in line:
                        continue
                    user_match = _USER_ID_RE.search(line)
                    title_match = _TITLE_RE.search(line)
                    if user_match is None or title_match is None:
                        continue
                    title = title_match.group(1).replace("\\'", "'").strip()
                    by_user.setdefault(int(user_match.group(1)), set()).add(title)
        except OSError as exc:
            TASK_LOG.warning('Robbo CSV: cannot read course interest log %s: %s', path, exc)
    return by_user


def _released_graded_test_percents(course_grade) -> List[float]:
    percents: List[float] = []
    for chapter in course_grade.chapter_grades.values():
        for section in chapter['sections']:
            if not section.graded or not section.show_grades(has_staff_access=False):
                continue
            graded_total = section.graded_total
            if graded_total is None or graded_total.possible <= 0:
                continue
            percents.append(round(100.0 * section.percent_graded, 2))
            if len(percents) >= _MAX_GRADED_TESTS:
                return percents
    return percents + ([0.0] * (_MAX_GRADED_TESTS - len(percents)))


def _slugify_interest_column(stub_id: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_]+', '_', stub_id.replace('-', '_')).strip('_').lower()


def _split_profile_feature_order(query_features: List[str]) -> tuple[List[str], List[str]]:
    """Leading columns, then Robbo block, then tail columns (see _TAIL_PROFILE_FEATURES)."""
    leading: List[str] = []
    tail: List[str] = []
    for feature in query_features:
        if feature in _TAIL_PROFILE_FEATURES:
            tail.append(feature)
        else:
            leading.append(feature)
    return leading, tail


def _middle_headers() -> List[str]:
    interest_headers = [
        f'interest_{_slugify_interest_column(stub["id"])}'
        for stub in get_robbo_catalog_stubs()
    ]
    return [
        'report_course_id',
        'company',
        *[f'test_{i}' for i in range(1, _MAX_GRADED_TESTS + 1)],
        *interest_headers,
    ]


def _users_enrolled_in_course(course_id):
    return (
        CourseEnrollment.objects.users_enrolled_in(course_id)
        .order_by('username')
        .select_related('profile')
    )


def _base_rows_by_username(course_id, query_features: Iterable[str]) -> Dict[str, Dict[str, object]]:
    return {
        row.get('username'): row
        for row in enrolled_students_features(course_id, query_features)
        if row.get('username')
    }


def upload_robbo_extended_students_csv(_xblock_instance_args, _entry_id, course_id, task_input, action_name):
    """
    Generate Robbo extended learner profile CSV and store it using the standard ReportStore.
    """
    start_time = time()
    start_date = datetime.now(UTC)
    users = list(_users_enrolled_in_course(course_id))
    task_progress = TaskProgress(action_name, len(users), start_time)

    current_step = {'step': 'Calculating Robbo extended profile info'}
    task_progress.update_task_state(extra_meta=current_step)

    query_features = list(task_input.get('features') or [])
    leading_features, tail_features = _split_profile_feature_order(query_features)
    header = [*leading_features, *_middle_headers(), *tail_features]
    base_rows = _base_rows_by_username(course_id, query_features)
    interest_from_logs = _interest_titles_from_logs()
    stubs = get_robbo_catalog_stubs()
    course = get_course_by_id(course_id, depth=0)

    rows = [header]
    with modulestore().bulk_operations(course_id):
        for user, course_grade, error in CourseGradeFactory().iter(users, course=course, course_key=course_id):
            profile = getattr(user, 'profile', None)
            if not course_grade:
                TASK_LOG.warning('Robbo CSV: grade read failed for user_id=%s: %s', user.id, error)
                percents = [0.0] * _MAX_GRADED_TESTS
            else:
                percents = _released_graded_test_percents(course_grade)

            interests = _interest_titles_from_profile(profile) | interest_from_logs.get(user.id, set())
            base_row = base_rows.get(user.username, {})
            rows.append([
                *[base_row.get(feature, '') for feature in leading_features],
                str(course_id),
                _company_from_profile(profile),
                *percents,
                *['yes' if stub['title'] in interests else 'no' for stub in stubs],
                *[base_row.get(feature, '') for feature in tail_features],
            ])

    task_progress.attempted = task_progress.succeeded = len(rows) - 1
    task_progress.skipped = task_progress.total - task_progress.attempted

    current_step = {'step': 'Uploading CSV'}
    task_progress.update_task_state(extra_meta=current_step)
    upload_csv_to_report_store(rows, 'robbo_student_profile_info', course_id, start_date)

    return task_progress.update_task_state(extra_meta=current_step)
