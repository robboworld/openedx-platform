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
from typing import Dict, FrozenSet, List, Set

from django.contrib.auth.models import User  # lint-amnesty, pylint: disable=imported-auth-user
from django.core.exceptions import ObjectDoesNotExist
from django.conf import settings
from completion.exceptions import UnavailableCompletionData
from completion.utilities import get_key_to_last_completed_block
from pytz import UTC
from xmodule.modulestore.django import modulestore
from xmodule.modulestore.exceptions import ItemNotFoundError, NoPathToItem
from xmodule.modulestore.search import path_to_location

from common.djangoapps.student.models import CourseEnrollment
from lms.djangoapps.courseware.robbo_catalog import get_robbo_catalog_stubs
from lms.djangoapps.grades.course_grade_factory import CourseGradeFactory
from lms.djangoapps.instructor_analytics.basic import learner_features_dict
from lms.djangoapps.program_enrollments.api import fetch_program_enrollments_by_students
from openedx.core.lib.courses import get_course_by_id

from .runner import TaskProgress
from .utils import upload_csv_to_report_store

TASK_LOG = logging.getLogger('edx.celery.task')

_INTEREST_META_KEY = 'robbo_course_interest_titles'
_MAX_GRADED_TESTS = 5
# Russian labels for leaf XBlock category in CSV ``theory_path`` (x.y.z) third segment.
_THEORY_BLOCK_TYPE_RU = {
    'html': 'текст',
    'video': 'видео',
    'problem': 'тестирование',
    'openassessment': 'оценивание',
    'library_content': 'библиотека',
    'poll': 'опрос',
    'survey': 'опрос',
    'word_cloud': 'облако_слов',
    'lti': 'lti',
    'drag-and-drop-v2': 'перетаскивание',
    'chapter': 'раздел',
    'sequential': 'подраздел',
    'vertical': 'блок',
    'course': 'курс',
}
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


# ``city`` and ``external_user_key`` are rendered at the far right (after tail columns).
# ``enrolled_in_report_course`` is inserted immediately after ``date_joined`` in the prefix.
_DEFERRED_TO_END_FEATURES: FrozenSet[str] = frozenset({'external_user_key', 'city'})


def _leading_without_trailer_columns(leading_features: List[str]) -> List[str]:
    return [f for f in leading_features if f not in _DEFERRED_TO_END_FEATURES]


def _prefix_column_names(leading_features: List[str]) -> List[str]:
    """Leading columns (no city/external at end); ``enrolled_in_report_course`` right after ``date_joined``."""
    names: List[str] = []
    inserted = False
    for feature in _leading_without_trailer_columns(leading_features):
        names.append(feature)
        if feature == 'date_joined':
            names.append('enrolled_in_report_course')
            inserted = True
    if not inserted:
        names.append('enrolled_in_report_course')
    return names


def _prefix_row_values(
    leading_features: List[str],
    base_row: Dict[str, object],
    user,
    course_id,
) -> List[object]:
    enrolled = 'yes' if CourseEnrollment.is_enrolled(user, course_id) else 'no'
    cells: List[object] = []
    inserted = False
    for feature in _leading_without_trailer_columns(leading_features):
        cells.append(base_row.get(feature, ''))
        if feature == 'date_joined':
            cells.append(enrolled)
            inserted = True
    if not inserted:
        cells.append(enrolled)
    return cells


def _trailer_column_names(leading_features: List[str]) -> List[str]:
    names = ['report_course_id']
    if 'external_user_key' in leading_features:
        names.append('external_user_key')
    if 'city' in leading_features:
        names.append('city')
    return names


def _trailer_row_values(
    leading_features: List[str],
    base_row: Dict[str, object],
    _user,
    course_id,
) -> List[object]:
    cells: List[object] = [str(course_id)]
    if 'external_user_key' in leading_features:
        cells.append(base_row.get('external_user_key', ''))
    if 'city' in leading_features:
        cells.append(base_row.get('city', ''))
    return cells


def _visible_child_index(parent_block, child_location) -> int:
    """1-based index of ``child_location`` among non-staff-only children of ``parent_block``; 0 if not found."""
    idx = 0
    for child in parent_block.get_children():
        if getattr(child, 'visible_to_staff_only', False):
            continue
        idx += 1
        if child.location == child_location:
            return idx
    return 0


def _theory_path_xyz(user, course_id) -> str:
    """
    Last completed block in the report course: ``section_index.subsection_index.type_ru`` (e.g. ``1.2.текст``).

    Uses the same completion source as resume / mobile "last visited" (last *completed* block).
    """
    try:
        block_key = get_key_to_last_completed_block(user, course_id)
    except UnavailableCompletionData:
        return ''

    store = modulestore()
    try:
        with store.bulk_operations(course_id):
            path = path_to_location(store, block_key, request=None, full_path=True)
    except (ItemNotFoundError, NoPathToItem) as exc:
        TASK_LOG.debug('Robbo CSV: theory_path path_to_location failed user_id=%s: %s', user.id, exc)
        return ''

    if not path or len(path) < 2:
        return ''

    try:
        course_block = store.get_item(path[0])
        chapter_block = store.get_item(path[1])
    except ItemNotFoundError:
        return ''

    x = _visible_child_index(course_block, path[1])
    y = 0
    if len(path) > 2:
        y = _visible_child_index(chapter_block, path[2])

    leaf = path[-1]
    block_type = getattr(leaf, 'block_type', '') or ''
    z = _THEORY_BLOCK_TYPE_RU.get(block_type, block_type or 'прочее')

    if x <= 0:
        return ''
    if y <= 0:
        return f'{x}.0.{z}'
    return f'{x}.{y}.{z}'


def _middle_headers() -> List[str]:
    interest_headers = [
        f'interest_{_slugify_interest_column(stub["id"])}'
        for stub in get_robbo_catalog_stubs()
    ]
    return [
        'company',
        'theory_path',
        *[f'test_{i}' for i in range(1, _MAX_GRADED_TESTS + 1)],
        *interest_headers,
    ]


def _all_users_for_robbo_csv(query_features: List[str]):
    """All platform users (Robbo extended CSV includes learners not enrolled in the report course)."""
    queryset = User.objects.all().order_by('username').select_related('profile')
    if 'cohort' in query_features:
        queryset = queryset.prefetch_related('course_groups')
    if 'team' in query_features:
        queryset = queryset.prefetch_related('teams')
    return list(queryset)


def _batch_external_user_key_map(users: List[User]) -> Dict[int, object]:
    mapping: Dict[int, object] = {}
    if not users:
        return mapping
    for program_enrollment in fetch_program_enrollments_by_students(users=users, realized_only=True):
        mapping[program_enrollment.user_id] = program_enrollment.external_user_key
    return mapping


def upload_robbo_extended_students_csv(_xblock_instance_args, _entry_id, course_id, task_input, action_name):
    """
    Generate Robbo extended learner profile CSV and store it using the standard ReportStore.

    Includes all platform users; ``enrolled_in_report_course`` marks active enrollment in the
    course this report was generated from (grades and tests still use that course context).

    Middle columns include ``theory_path`` (``section.subsection.type_ru`` from last completed block)
    immediately before ``test_1``..``test_5``.
    """
    start_time = time()
    start_date = datetime.now(UTC)

    query_features = list(task_input.get('features') or [])
    users = _all_users_for_robbo_csv(query_features)
    task_progress = TaskProgress(action_name, len(users), start_time)

    current_step = {'step': 'Calculating Robbo extended profile info'}
    task_progress.update_task_state(extra_meta=current_step)

    leading_features, tail_features = _split_profile_feature_order(query_features)
    header = [
        *_prefix_column_names(leading_features),
        *_middle_headers(),
        *tail_features,
        *_trailer_column_names(leading_features),
    ]
    external_map: Dict[int, object] = {}
    if 'external_user_key' in query_features and users:
        external_map = _batch_external_user_key_map(users)
    interest_from_logs = _interest_titles_from_logs()
    stubs = get_robbo_catalog_stubs()
    course = get_course_by_id(course_id, depth=0)

    rows = [header]
    with modulestore().bulk_operations(course_id):
        for user, course_grade, error in CourseGradeFactory().iter(users, course=course, course_key=course_id):
            try:
                profile = user.profile
            except ObjectDoesNotExist:
                profile = None
            if not course_grade:
                if CourseEnrollment.is_enrolled(user, course_id):
                    TASK_LOG.warning('Robbo CSV: grade read failed for user_id=%s: %s', user.id, error)
                percents = [0.0] * _MAX_GRADED_TESTS
            else:
                percents = _released_graded_test_percents(course_grade)

            interests = _interest_titles_from_profile(profile) | interest_from_logs.get(user.id, set())
            base_row = learner_features_dict(user, course_id, query_features, external_map)
            theory_path = _theory_path_xyz(user, course_id)
            rows.append([
                *_prefix_row_values(leading_features, base_row, user, course_id),
                _company_from_profile(profile),
                theory_path,
                *percents,
                *['yes' if stub['title'] in interests else 'no' for stub in stubs],
                *[base_row.get(feature, '') for feature in tail_features],
                *_trailer_row_values(leading_features, base_row, user, course_id),
            ])

    task_progress.attempted = task_progress.succeeded = len(rows) - 1
    task_progress.skipped = task_progress.total - task_progress.attempted

    current_step = {'step': 'Uploading CSV'}
    task_progress.update_task_state(extra_meta=current_step)
    upload_csv_to_report_store(rows, 'robbo_student_profile_info', course_id, start_date)

    return task_progress.update_task_state(extra_meta=current_step)
