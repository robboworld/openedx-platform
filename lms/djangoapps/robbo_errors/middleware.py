# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (human-readable errors). See NOTICE at repository root.
"""
Server errors into the journal, and a human answer for AJAX and API calls that crash.

First in ``MIDDLEWARE``, so its ``process_exception`` runs last: exceptions other middleware turn
into answers (courseware redirects, rate limits) never reach it. What reaches it is a real crash:
it goes to the journal with its traceback, and an AJAX or API call gets the JSON of ``SRV-ERROR``
instead of the HTML of the 500 page (pages keep the themed 500 page from ``handler500``).

Crashes outside views (in other middleware) reach Django's ``got_request_exception`` signal
instead, which ``apps.py`` connects to ``journal_uncaught_exception``.
"""

import logging
import sys
import traceback

from django.core.exceptions import BadRequest, PermissionDenied, SuspiciousOperation
from django.http import Http404, JsonResponse

from .ids import request_incident_id
from .responses import error_payload, journal_request, wants_json

log = logging.getLogger(__name__)

# Django turns these into 400/403/404 answers; they are not crashes.
EXPECTED_EXCEPTIONS = (Http404, PermissionDenied, SuspiciousOperation, BadRequest)


def _journal_crash(request, exception):
    if getattr(request, '_robbo_crash_journaled', False):
        return
    request._robbo_crash_journaled = True
    try:
        journal_request(
            request, 'SRV-ERROR', 500,
            developer_message=f'{type(exception).__module__}.{type(exception).__name__}: {exception}',
            traceback=''.join(traceback.format_exception(type(exception), exception, exception.__traceback__)),
        )
    except Exception:  # pylint: disable=broad-except
        log.exception('robbo_errors: could not journal a crash')


def journal_uncaught_exception(sender, request=None, **kwargs):  # pylint: disable=unused-argument
    """``got_request_exception`` receiver: a crash Django answers with its 500 handler."""
    exception = sys.exc_info()[1]
    if request is None or exception is None or isinstance(exception, EXPECTED_EXCEPTIONS):
        return
    _journal_crash(request, exception)


class RobboErrorsMiddleware:
    """Incident number for every request, crashes into the journal, JSON crash answers for AJAX."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_incident_id(request)
        response = self.get_response(request)
        # Behind Caddy the number already is in the answer (Caddy adds X-Request-ID to all of them);
        # without Caddy, give errors the number this request got here.
        if response.status_code >= 400 and getattr(request, '_robbo_incident_generated', False):
            response.setdefault('X-Request-ID', request_incident_id(request))
        return response

    def process_exception(self, request, exception):
        if isinstance(exception, EXPECTED_EXCEPTIONS):
            return None
        _journal_crash(request, exception)
        if not wants_json(request):
            return None
        try:
            payload = error_payload(
                request, 'SRV-ERROR', developer_message=f'{type(exception).__name__}',
            )
        except Exception:  # pylint: disable=broad-except
            log.exception('robbo_errors: could not build the error answer')
            return None
        # Answered here, Django will not log it: keep the traceback in the log as its handler would.
        log.error(
            'Internal Server Error: %s (incident %s)', request.path, request_incident_id(request),
            exc_info=(type(exception), exception, exception.__traceback__),
        )
        return JsonResponse(payload, status=500)
