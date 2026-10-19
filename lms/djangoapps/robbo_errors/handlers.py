# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (human-readable errors). See NOTICE at repository root.
"""
Django's error handlers for the LMS and Studio (``handler400/403/404/500`` in ``lms/urls.py`` and
``cms/urls.py``, ``CSRF_FAILURE_VIEW``): the error page with a code and number, or the JSON answer
for AJAX. Before, the LMS showed Django's bare English pages for 400, 403 and CSRF, Studio had no
403 page at all and answered AJAX with English sentences its notifications showed as they were.
"""

from django_ratelimit.exceptions import Ratelimited

from common.djangoapps.util.views import fix_crum_request

from .pages import error_answer


def _detail(exception):
    return f'{type(exception).__name__}: {exception}' if exception else ''


@fix_crum_request
def handler400(request, exception=None):
    return error_answer(request, 'BAD-INPUT', 400, developer_message=_detail(exception))


@fix_crum_request
def handler403(request, exception=None):
    if isinstance(exception, Ratelimited):
        return handler429(request, exception)
    return error_answer(request, 'ACCESS-DENIED', 403, developer_message=_detail(exception))


@fix_crum_request
def handler404(request, exception=None):  # pylint: disable=unused-argument
    # Not counted: most 404s are bots and stale links, the counter would say nothing.
    return error_answer(request, 'NOT-FOUND', 404, journal=False)


@fix_crum_request
def handler429(request, exception=None):
    return error_answer(request, 'TOO-MANY', 429, developer_message=_detail(exception))


@fix_crum_request
def handler500(request):
    # The crash itself is already in the journal (RobboErrorsMiddleware), with the same number.
    return error_answer(request, 'SRV-ERROR', 500, journal=False)


@fix_crum_request
def csrf_failure(request, reason=''):
    return error_answer(request, 'PAGE-STALE', 403, developer_message=f'CSRF: {reason}')
