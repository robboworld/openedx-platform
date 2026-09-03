# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (openedx-platform fork).
# See NOTICE at repository root.

"""
Parse course catalog interest events from LMS application logs for instructor reports.
"""
from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Tuple

from django.conf import settings
from django.http import HttpResponse
from django.utils.translation import gettext as _

from lms.djangoapps.instructor_analytics import csvs as instructor_analytics_csvs

_INTEREST_LINE_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+) .* course_interest submitted: "
    r"stub_id=\S+ "
    r"course_title='((?:\\'|[^'])*)' "
    r"user_id=\d+ "
    r"email='((?:\\'|[^'])*)' "
    r"full_name='((?:\\'|[^'])*)' "
    r"company='((?:\\'|[^'])*)'"
)

QUERY_FEATURES = ('full_name', 'email', 'company', 'course_title')


def _unescape_log_field(value: str) -> str:
    return value.replace("\\'", "'").strip()


def course_interest_log_paths() -> List[str]:
    configured = getattr(settings, 'ROBBO_COURSE_INTEREST_LOG_PATHS', [])
    if isinstance(configured, str):
        configured = [configured]
    if isinstance(configured, (list, tuple)):
        paths = [path for path in configured if path and os.path.isfile(path)]
        if paths:
            return paths

    log_dir = getattr(settings, 'LOG_DIR', None)
    if log_dir:
        candidate = os.path.join(log_dir, 'all.log')
        if os.path.isfile(candidate):
            return [candidate]
    return []


def iter_course_interest_rows_from_logs() -> List[Dict[str, str]]:
    """
    Return one dict per matching log line (newest file order preserved, chronological within file).
    """
    rows: List[Dict[str, str]] = []
    for path in course_interest_log_paths():
        try:
            with open(path, encoding='utf-8', errors='replace') as log_file:
                for line in log_file:
                    match = _INTEREST_LINE_RE.search(line)
                    if match is None:
                        continue
                    rows.append({
                        'id': len(rows) + 1,
                        'full_name': _unescape_log_field(match.group(4)),
                        'email': _unescape_log_field(match.group(3)),
                        'company': _unescape_log_field(match.group(5)),
                        'course_title': _unescape_log_field(match.group(2)),
                    })
        except OSError:
            continue
    return rows


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
