# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (human-readable errors). See NOTICE at repository root.
"""
- ``report``: errors only the browser saw (no answer from the server, a crashed MFE page, an
  answer Caddy gave by itself) come here to be journaled.
- ``lookup`` and ``incident``: the support page, found by the code from the user's screen.
  It is not in Django admin on purpose: admin needs ``is_staff``, which in Open edX also makes the
  account staff of every course. Here the ``robbo_errors.view_errorincident`` permission is enough
  (the «Поддержка» group has it, superusers have all permissions).
"""

import json
import re
from datetime import timedelta
from urllib.parse import urlsplit

from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django_ratelimit.decorators import ratelimit

from . import catalog
from .ids import normalize, parse_query
from .journal import record
from .models import ErrorIncident
from .responses import LEARNER, STAFF, audience

REPORT_MAX_BYTES = 8 * 1024
VIEW_PERMISSION = 'robbo_errors.view_errorincident'
SEARCH_LIMIT = 100

_CODE_RE = re.compile(r'^[A-Z]+(?:-[A-Z]+)+$')
_SOURCE_RE = re.compile(r'^[a-z0-9:_-]+$')
_METHOD_RE = re.compile(r'^[A-Z]+$')


def _text(data, key, limit):
    value = data.get(key)
    return str(value)[:limit] if value is not None else ''


def _path(url):
    """Path of a URL without the query string and fragment: they may carry tokens or personal data."""
    return urlsplit(url).path if url else ''


def _host(url):
    return urlsplit(url).netloc if url else ''


# sendBeacon cannot add a CSRF header and sends the JSON as text/plain (no CORS preflight from
# the apps.* host). The request changes nothing but the journal, and the rate limit plus the
# journal's own cap keep a forged flood small.
@csrf_exempt
@require_POST
@ratelimit(key='openedx.core.djangoapps.util.ratelimit.real_ip', rate='60/m', method='POST', block=False)
def report(request):
    if getattr(request, 'limited', False) or len(request.body) > REPORT_MAX_BYTES:
        return HttpResponse(status=204)
    try:
        data = json.loads(request.body.decode('utf-8'))
    except (UnicodeDecodeError, ValueError):
        return HttpResponseBadRequest()
    if not isinstance(data, dict):
        return HttpResponseBadRequest()

    code = _text(data, 'code', 64).upper()
    if not _CODE_RE.match(code):
        code = 'APP-CRASH'
    source = _text(data, 'source', 64).lower()
    if not _SOURCE_RE.match(source):
        source = 'browser'
    method = _text(data, 'method', 10).upper()
    try:
        status = int(data.get('status')) if data.get('status') not in (None, '') else None
    except (TypeError, ValueError):
        status = None
    if status is not None and not 0 <= status <= 599:
        status = None
    url, page = _text(data, 'url', 2048), _text(data, 'page', 2048)
    who = _text(data, 'audience', 16)

    record(
        code,
        incident_id=normalize(_text(data, 'incident_id', 64)),
        source=source,
        status=status,
        site=_host(url) or _host(page),
        method=method if _METHOD_RE.match(method) else '',
        path=_path(url),
        page=_path(page),
        user=request.user,
        audience=who if who in (LEARNER, STAFF) else audience(request.user),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        developer_message=_text(data, 'message', 2000),
    )
    return HttpResponse(status=204)


def _require_support(request):
    if not request.user.has_perm(VIEW_PERMISSION):
        raise Http404  # the page does not exist for everyone else


def _context(request, **extra):
    return {
        **admin.site.each_context(request),
        # The admin sidebar would list models support cannot open.
        'is_nav_sidebar_enabled': False,
        'title': 'Журнал ошибок',
        **extra,
    }


def _search(query):
    number, code = parse_query(query)
    incidents = ErrorIncident.objects.select_related('user')
    if number:
        # The number decides: a code misread from the screen must not hide the row.
        return incidents.filter(Q(incident_id__startswith=number) | Q(merged_ids__contains=number)), number, code
    if code and catalog.get(code):
        return incidents.filter(code=code), number, code
    # A login such as claude-learner also looks like a code.
    return incidents.filter(Q(user__username=query) | Q(user__email__iexact=query)), None, None


def _summary():
    """Per code: occurrences today, in 7 and in 30 days — what to fix first."""
    now = timezone.now()
    periods = {
        'today': now.replace(hour=0, minute=0, second=0, microsecond=0),
        'week': now - timedelta(days=7),
        'month': now - timedelta(days=30),
    }
    rows = {}
    for period, since in periods.items():
        totals = (
            ErrorIncident.objects.filter(last_seen__gte=since)
            .values('code').annotate(total=Sum('count'), users=Count('user', distinct=True))
        )
        for item in totals:
            row = rows.setdefault(item['code'], {'code': item['code'], 'today': 0, 'week': 0, 'month': 0})
            row[period] = item['total']
            if period == 'week':
                row['users'] = item['users']
    for row in rows.values():
        kind = catalog.get(row['code'])
        row['title'] = kind.title['ru'] if kind else ''
        row['journal'] = kind.journal if kind else 'case'
    return sorted(rows.values(), key=lambda row: (-row['week'], -row['month'], row['code']))


@login_required
@require_GET
def lookup(request):
    _require_support(request)
    query = request.GET.get('q', '').strip()
    if not query:
        kinds = [
            {'code': kind.code, 'title': kind.title, 'support': kind.support,
             'message_ru': catalog.describe(kind.code, lang='ru').message}
            for kind in catalog.codes().values()
        ]
        return render(request, 'robbo_errors/lookup.html', _context(
            request, summary=_summary(), kinds=kinds, query='',
        ))
    incidents, number, code = _search(query)
    return render(request, 'robbo_errors/lookup.html', _context(
        request,
        query=query,
        number=number,
        code=code,
        incidents=list(incidents[:SEARCH_LIMIT]),
        search_limit=SEARCH_LIMIT,
    ))


@login_required
@require_GET
def incident(request, pk):
    _require_support(request)
    row = get_object_or_404(ErrorIncident.objects.select_related('user'), pk=pk)
    kind = catalog.get(row.code)
    return render(request, 'robbo_errors/incident.html', _context(
        request,
        title=f'Случай {row}',
        incident=row,
        kind=kind,
        user_text=catalog.describe(row.code, lang='ru'),
        merged_numbers=[f'{n[:4].upper()}-{n[4:].upper()}' for n in row.merged_ids.split()],
    ))
