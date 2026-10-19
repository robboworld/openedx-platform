# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (human-readable errors). See NOTICE at repository root.
"""
Incident numbers. Caddy gives every request a UUID (``X-Request-ID``); the same number is in the
Caddy response, in the journal and on the user's screen as its first 8 hex digits: ``7F3A-29C1``.
"""

import re
import uuid

REQUEST_ID_HEADER = 'HTTP_X_REQUEST_ID'
_REQUEST_ID_RE = re.compile(r'^[0-9a-fA-F-]{8,64}$')
# 8 hex digits with an optional dash in the middle, not glued to other letters or digits (so the
# hex-looking part of a code such as ACCESS-DENIED or a word is not taken for a number).
_NUMBER_RE = re.compile(r'(?<![0-9A-Z])([0-9A-F]{4})-?([0-9A-F]{4})(?![0-9A-Z])')
_CODE_RE = re.compile(r'(?<![0-9A-Z-])([A-Z]+(?:-[A-Z]+)+)(?![0-9A-Z-])')


def normalize(raw):
    """Hex digits of a request id (UUID with or without dashes), or ``''`` when it is not one."""
    raw = (raw or '').strip()
    if not _REQUEST_ID_RE.match(raw):
        return ''
    digits = raw.replace('-', '').lower()
    return digits[:32] if len(digits) >= 8 else ''


def request_incident_id(request):
    """
    The incident number of ``request``: Caddy's ``X-Request-ID``, or a new one when the request did
    not come through Caddy (tests, direct calls to the container). Stable within the request.
    """
    incident_id = getattr(request, '_robbo_incident_id', None)
    if incident_id is None:
        incident_id = normalize(request.META.get(REQUEST_ID_HEADER))
        request._robbo_incident_generated = not incident_id
        incident_id = incident_id or uuid.uuid4().hex
        request._robbo_incident_id = incident_id
    return incident_id


def short_id(incident_id):
    """``7F3A-29C1`` for the user; ``''`` for an empty id (per-day counters have none)."""
    head = (incident_id or '')[:8].upper()
    return f'{head[:4]}-{head[4:]}' if len(head) == 8 else ''


def parse_query(query):
    """
    What support pasted into the search: ``(number, code)``, each ``None`` when absent. Accepts the
    whole line from the user's screen (``Код: UPLOAD-SIZE · 7F3A-29C1``), the number alone in any
    case, with or without the dash, or a full request UUID.
    """
    text = (query or '').upper()
    number = _NUMBER_RE.search(text)
    code = _CODE_RE.search(text)
    return (
        (number.group(1) + number.group(2)).lower() if number else None,
        code.group(1) if code else None,
    )
