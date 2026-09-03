# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (openedx-platform fork).
# See NOTICE at repository root.

"""
Parse course catalog interest events from LMS application and tracking logs.
"""
from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Set, Tuple

from django.conf import settings
from django.http import HttpResponse
from django.utils.translation import gettext as _

from lms.djangoapps.instructor_analytics import csvs as instructor_analytics_csvs

# Application log line written by robbo.course_interest.
_INTEREST_LINE_RE = re.compile(
    r"course_interest submitted: "
    r"stub_id=\S+ "
    r"course_title='((?:\\'|[^'])*)' "
    r"user_id=(\d+) "
    r"email='((?:\\'|[^'])*)' "
    r"full_name='((?:\\'|[^'])*)' "
    r"company='((?:\\'|[^'])*)'"
)

# Structured tracking event name (see robbo_course_interest.course_interest).
TRACKING_EVENT_NAME = 'robbo.course_interest'

_DEFAULT_LOG_BASENAMES = ('all.log', 'tracking.log')

QUERY_FEATURES = ('full_name', 'email', 'company', 'course_title')


def _unescape_log_field(value: str) -> str:
    return value.replace("\\'", "'").strip()


def course_interest_log_paths() -> List[str]:
    """
    Log files to scan for course-interest events.

    Prefer ``ROBBO_COURSE_INTEREST_LOG_PATHS`` when set; otherwise
    ``LOG_DIR/all.log`` and ``LOG_DIR/tracking.log`` when present.
    """
    configured = getattr(settings, 'ROBBO_COURSE_INTEREST_LOG_PATHS', [])
    if isinstance(configured, str):
        configured = [configured]
    if isinstance(configured, (list, tuple)):
        paths = [path for path in configured if path and os.path.isfile(path)]
        if paths:
            return paths

    log_dir = getattr(settings, 'LOG_DIR', None)
    if not log_dir:
        return []
    return [
        candidate
        for name in _DEFAULT_LOG_BASENAMES
        for candidate in [os.path.join(log_dir, name)]
        if os.path.isfile(candidate)
    ]


def _row_from_app_log_match(match: re.Match) -> Dict[str, str]:
    return {
        'full_name': _unescape_log_field(match.group(4)),
        'email': _unescape_log_field(match.group(3)),
        'company': _unescape_log_field(match.group(5)),
        'course_title': _unescape_log_field(match.group(1)),
        'user_id': match.group(2),
    }


def _parse_tracking_json_payload(line: str) -> Dict | None:
    marker = ' - {'
    idx = line.find(marker)
    if idx < 0:
        return None
    try:
        return json.loads(line[idx + 3:])
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def _coerce_event_dict(event) -> Dict:
    if isinstance(event, dict):
        return event
    if isinstance(event, str):
        try:
            parsed = json.loads(event)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _row_from_tracking_payload(payload: Dict) -> Dict[str, str] | None:
    name = payload.get('name') or payload.get('event_type') or ''
    if name != TRACKING_EVENT_NAME and 'robbo.course_interest' not in str(name):
        return None

    event = _coerce_event_dict(payload.get('event'))
    context = payload.get('context') if isinstance(payload.get('context'), dict) else {}

    title = str(event.get('course_title') or event.get('title') or '').strip()
    if not title:
        return None

    user_id = event.get('user_id')
    if user_id is None:
        user_id = context.get('user_id')
    if user_id is None:
        return None

    return {
        'full_name': str(event.get('full_name') or '').strip(),
        'email': str(event.get('email') or '').strip(),
        'company': str(event.get('company') or '').strip(),
        'course_title': title,
        'user_id': str(user_id),
    }


def _iter_interest_records_from_line(line: str) -> List[Dict[str, str]]:
    records: List[Dict[str, str]] = []
    app_match = _INTEREST_LINE_RE.search(line)
    if app_match is not None:
        records.append(_row_from_app_log_match(app_match))

    if 'robbo.course_interest' in line or 'course_interest submitted' in line:
        payload = _parse_tracking_json_payload(line)
        if payload is not None:
            tracking_row = _row_from_tracking_payload(payload)
            if tracking_row is not None:
                records.append(tracking_row)
    return records


def iter_course_interest_rows_from_logs() -> List[Dict[str, str]]:
    """
    Return one dict per matching log line (file order, chronological within file).

    Deduplicates identical (user_id, course_title, email) rows across all.log and
    tracking.log so the instructor table does not double-count the same event.
    """
    rows: List[Dict[str, str]] = []
    seen: Set[Tuple[str, str, str]] = set()
    for path in course_interest_log_paths():
        try:
            with open(path, encoding='utf-8', errors='replace') as log_file:
                for line in log_file:
                    for record in _iter_interest_records_from_line(line):
                        key = (
                            record.get('user_id', ''),
                            record.get('course_title', ''),
                            record.get('email', ''),
                        )
                        if key in seen:
                            continue
                        seen.add(key)
                        rows.append({
                            'id': len(rows) + 1,
                            'full_name': record.get('full_name', ''),
                            'email': record.get('email', ''),
                            'company': record.get('company', ''),
                            'course_title': record.get('course_title', ''),
                        })
        except OSError:
            continue
    return rows


def interest_titles_by_user_from_logs() -> Dict[int, Set[str]]:
    """
    Map user_id → set of interested course titles from all.log / tracking.log.

    Used by the Robbo extended learner profile CSV (``interest_*`` columns).
    """
    by_user: Dict[int, Set[str]] = {}
    for path in course_interest_log_paths():
        try:
            with open(path, encoding='utf-8', errors='replace') as log_file:
                for line in log_file:
                    for record in _iter_interest_records_from_line(line):
                        try:
                            user_id = int(record['user_id'])
                        except (KeyError, TypeError, ValueError):
                            continue
                        title = (record.get('course_title') or '').strip()
                        if not title:
                            continue
                        by_user.setdefault(user_id, set()).add(title)
        except OSError:
            continue
    return by_user


def course_interest_table_payload() -> Tuple[List[str], Dict[str, str], List[Dict[str, str]]]:
    feature_names = {
        'full_name': _('ФИО'),
        'email': _('Почта'),
        'company': _('Компания'),
        'course_title': _('Интересующий курс'),
    }
    return list(QUERY_FEATURES), feature_names, iter_course_interest_rows_from_logs()


def course_interest_csv_response() -> HttpResponse:
    """
    Build a CSV attachment for catalog course-interest rows from LMS logs.
    """
    query_features, feature_names, rows = course_interest_table_payload()
    __, data_rows = instructor_analytics_csvs.format_dictlist(rows, query_features)
    header = [str(feature_names[feature]) for feature in query_features]
    return instructor_analytics_csvs.create_csv_response(
        'robbo_course_interest.csv',
        header,
        data_rows,
    )
