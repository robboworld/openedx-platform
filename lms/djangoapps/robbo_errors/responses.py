# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (human-readable errors). See NOTICE at repository root.
"""
The JSON shape of an error answer (docs/human-errors.md §4) and the helper Robbo views use for it.

It extends the upstream ``DeveloperErrorViewMixin`` shape (``developer_message``, ``error_code``),
and repeats the user's message as a plain ``error`` string: Studio's global AJAX handler shows
``response.error`` as is, so old Studio pages show the human text without changes on their side.
"""

from django.conf import settings
from django.http import JsonResponse

from common.djangoapps.student.models import CourseAccessRole

from . import catalog
from .ids import request_incident_id
from .journal import record

LEARNER = 'learner'
STAFF = 'staff'


def audience(user):
    """
    Whom the message sends further: a learner to their teacher (or support), course staff and
    authors to support (docs/human-errors.md). Any course role counts as staff.
    """
    if user is None or not user.is_authenticated:
        return LEARNER
    if user.is_staff or CourseAccessRole.objects.filter(user=user).exists():
        return STAFF
    return LEARNER


def wants_json(request):
    """``True`` for AJAX and API calls, ``False`` for a page the browser navigates to."""
    accept = request.META.get('HTTP_ACCEPT', '')
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return True
    if 'text/html' in accept:
        return False
    return 'json' in accept or request.path.startswith('/api/')


def source_of():
    """``lms`` or ``cms``: which service answered (both share the journal)."""
    return 'cms' if settings.ROOT_URLCONF.startswith('cms') else 'lms'


def journal_request(request, code, status, developer_message='', traceback=''):
    """Write an error of ``request`` to the journal with what the request itself tells."""
    user = getattr(request, 'user', None)
    return record(
        code,
        incident_id=request_incident_id(request),
        source=source_of(),
        status=status,
        # Raw header, not get_host(): an error answer must not fail on a host Django would reject.
        site=request.META.get('HTTP_HOST', ''),
        method=request.method or '',
        path=request.path,
        user=user,
        audience=audience(user),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        developer_message=developer_message,
        traceback=traceback,
    )


def error_payload(request, code, developer_message='', **params):
    """The JSON body of an error answer; ``params`` fill the message (e.g. ``limit=50``)."""
    text = catalog.describe(code, **params)
    return {
        'error_code': code,
        'user_title': text.title,
        'user_message': text.message,
        'incident_id': request_incident_id(request),
        'audience': audience(getattr(request, 'user', None)),
        'developer_message': developer_message,
        'error': text.message,
    }


def robbo_error(request, code, status=None, developer_message='', **params):
    """
    Answer ``request`` with error ``code`` of the catalog and write it to the journal::

        return robbo_error(request, 'GROUP-LINK-EXPIRED', developer_message=f'invite {code} revoked')

    ``status`` defaults to the code's own; ``developer_message`` is for logs and the journal only.
    """
    kind = catalog.get(code)
    status = status or (kind.status if kind and kind.status else 400)
    journal_request(request, code, status, developer_message=developer_message)
    return JsonResponse(error_payload(request, code, developer_message, **params), status=status)
