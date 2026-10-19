# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (human-readable errors). See NOTICE at repository root.
"""
Writing to the error journal, protected against floods: a page that fails in a loop, or an outage
that hits every user at once, must not fill the database (courses had a 20 GB log in October 2026).

- Repeats of one error (same code, source, site, path and user) within ``MERGE_WINDOW`` add to the
  ``count`` of one row; their numbers go to ``merged_ids`` so support still finds them.
- Codes with ``journal: count`` keep one counter row per code, source and site per day.
- Above ``ROBBO_ERRORS_MAX_PER_MINUTE`` writes per minute (per cache), new errors only reach the log.
- About every ``PURGE_EVERY``-th write deletes rows older than ``ROBBO_ERRORS_RETENTION_DAYS``.

The journal must never turn an error into a worse one: every failure here is logged and swallowed.
"""

import logging
import random
import uuid
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError
from django.db.models import F
from django.utils import timezone

from . import catalog
from .ids import short_id
from .models import ErrorIncident

log = logging.getLogger(__name__)

MERGE_WINDOW = timedelta(minutes=1)
MAX_MERGED_IDS_CHARS = 900  # ~100 numbers; later repeats only add to the count
PURGE_EVERY = 200
PURGE_BATCH = 1000

# Field sizes of ErrorIncident: a report must not fail on a long value.
_LIMITS = {
    'site': 255, 'source': 64, 'method': 10, 'path': 512, 'page': 512,
    'audience': 16, 'user_agent': 255, 'developer_message': 2000, 'traceback': 20000,
}


def _setting(name, default):
    return getattr(settings, name, default)


def _under_cap(now):
    """``False`` once this minute's writes reached ``ROBBO_ERRORS_MAX_PER_MINUTE``."""
    key = f'robbo_errors:writes:{now:%Y%m%d%H%M}'
    try:
        cache.add(key, 0, timeout=120)
        writes = cache.incr(key)
    except Exception:  # pylint: disable=broad-except
        return True  # no cache, no cap: better a few extra rows than lost errors
    limit = _setting('ROBBO_ERRORS_MAX_PER_MINUTE', 300)
    if writes == limit + 1:
        log.warning('robbo_errors: more than %s errors this minute, the rest only go to the log', limit)
    return writes <= limit


def _maybe_purge(now):
    if random.randrange(PURGE_EVERY):
        return
    cutoff = now - timedelta(days=_setting('ROBBO_ERRORS_RETENTION_DAYS', 90))
    ids = list(ErrorIncident.objects.filter(last_seen__lt=cutoff).values_list('id', flat=True)[:PURGE_BATCH])
    if ids:
        ErrorIncident.objects.filter(id__in=ids).delete()


def _clip(fields):
    return {name: (value or '')[:_LIMITS[name]] if name in _LIMITS else value for name, value in fields.items()}


def record(code, *, incident_id='', source, status=None, site='', method='', path='', page='', user=None,
           audience='', user_agent='', developer_message='', traceback=''):
    """
    Write one occurrence of ``code`` to the journal. Returns the row it went to, or ``None`` when
    only a day counter grew, the minute's cap was reached or the database failed. ``user`` may be
    anonymous; ``path`` and ``page`` must have no query string.
    """
    now = timezone.now()
    incident_id = incident_id or uuid.uuid4().hex  # a case without a number could never be found
    log.info('robbo_errors: %s %s %s %s %s', code, short_id(incident_id) or '-', status or '-', source, path)
    if not _under_cap(now):
        return None
    user = user if user is not None and user.is_authenticated else None
    kind = catalog.get(code)
    fields = _clip({
        'site': site, 'source': source, 'method': method, 'path': path, 'page': page, 'audience': audience,
        'user_agent': user_agent, 'developer_message': developer_message, 'traceback': traceback,
    })
    try:
        if kind is not None and kind.journal == 'count':
            row = _count(code, status, fields, now)
        else:
            row = _case(code, incident_id, status, user, fields, now)
        _maybe_purge(now)
        return row
    except DatabaseError:
        log.exception('robbo_errors: could not write %s %s to the journal', code, short_id(incident_id))
        return None


def _count(code, status, fields, now):
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    key = {'code': code, 'source': fields['source'], 'site': fields['site'], 'incident_id': ''}
    updated = ErrorIncident.objects.filter(first_seen__gte=day_start, **key).update(
        count=F('count') + 1, last_seen=now,
    )
    if updated:
        return None
    return ErrorIncident.objects.create(
        status=status, first_seen=now, last_seen=now, **key,
        # A counter is not one user's error: keep only what is the same for all of them.
        method=fields['method'],
    )


def _case(code, incident_id, status, user, fields, now):
    same = ErrorIncident.objects.filter(
        code=code, source=fields['source'], site=fields['site'], path=fields['path'], user=user,
        last_seen__gte=now - MERGE_WINDOW,
    ).exclude(incident_id='').order_by('-last_seen').first()
    if same is not None:
        merged = same.merged_ids
        number = short_id(incident_id).replace('-', '').lower()
        if number and number not in merged and len(merged) < MAX_MERGED_IDS_CHARS:
            merged = f'{merged} {number}'.strip()
        ErrorIncident.objects.filter(pk=same.pk).update(count=F('count') + 1, last_seen=now, merged_ids=merged)
        return same
    return ErrorIncident.objects.create(
        code=code, incident_id=incident_id, status=status, user=user, first_seen=now, last_seen=now, **fields,
    )
