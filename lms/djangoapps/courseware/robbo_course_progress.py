# Copyright (C) 2024-2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of the Robbo Open edX distribution. See NOTICE at repository root.

"""
Cached unit-completion progress for the /courses catalog and the learner dashboard.

``get_course_blocks_completion_summary`` builds the per-user block tree (~50 ms per course),
so both pages used to pay it for every enrollment on every load. Results are cached in the
Django cache under a key that changes whenever the progress can change:

* ``CourseOverview.modified`` — bumped when the course is published from Studio;
* the latest ``BlockCompletion.modified`` for the user in that course — bumped on any
  completion. All of them are fetched with one indexed query (user, course_key, modified).

The TTL only covers rare access changes (enrollment mode, cohorts, gating).
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict, Iterable, Optional

from completion.models import BlockCompletion
from django.core.cache import cache
from django.db.models import Max

log = logging.getLogger(__name__)

PROGRESS_CACHE_TTL = 60 * 60
_NO_UNITS = {'total': 0}


def _ts(value) -> str:
    return value.isoformat() if value else '-'


def _cache_key(user_id, course_key, overview_modified, last_completion) -> str:
    raw = f'{user_id}|{course_key}|{_ts(overview_modified)}|{_ts(last_completion)}'
    return 'robbo:course_progress:v1:' + hashlib.md5(raw.encode('utf-8')).hexdigest()


def _compute_progress(user, course_key) -> Dict[str, int]:
    from lms.djangoapps.courseware.courses import get_course_blocks_completion_summary  # pylint: disable=import-outside-toplevel

    summary = get_course_blocks_completion_summary(course_key, user)
    complete = int(summary.get('complete_count') or 0)
    incomplete = int(summary.get('incomplete_count') or 0)
    total = complete + incomplete
    if total <= 0:
        return dict(_NO_UNITS)
    return {
        'completed': complete,
        'total': total,
        'percent': min(100, max(0, round(100 * complete / total))),
    }


def get_courses_progress(user, course_overviews: Iterable[Any]) -> Dict[Any, Optional[Dict[str, int]]]:
    """
    Progress by course key: ``{'completed', 'total', 'percent'}``, or None when the course
    has no countable units or the summary could not be built.
    """
    overviews = {co.id: co for co in course_overviews if co is not None}
    if not overviews or not getattr(user, 'id', None):
        return {}

    last_completions = dict(
        BlockCompletion.objects.filter(user=user, context_key__in=list(overviews))
        .values('context_key')
        .annotate(last=Max('modified'))
        .values_list('context_key', 'last')
    )
    keys = {
        course_key: _cache_key(user.id, course_key, getattr(co, 'modified', None), last_completions.get(course_key))
        for course_key, co in overviews.items()
    }
    cached = cache.get_many(list(keys.values()))

    result: Dict[Any, Optional[Dict[str, int]]] = {}
    to_cache: Dict[str, Dict[str, int]] = {}
    for course_key, key in keys.items():
        progress = cached.get(key)
        if progress is None:
            try:
                progress = _compute_progress(user, course_key)
            except Exception as ex:  # pylint: disable=broad-except
                log.debug('Unable to load course progress for %s: %s', course_key, ex)
                result[course_key] = None
                continue
            to_cache[key] = progress
        result[course_key] = progress if progress.get('total') else None

    if to_cache:
        cache.set_many(to_cache, PROGRESS_CACHE_TTL)
    return result
