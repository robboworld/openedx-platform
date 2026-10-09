# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (site changelog). See NOTICE at repository root.
"""
API of the «Что нового» header button, shared by LMS pages and every MFE header.

Plain Django views on the LMS session: MFEs call them with ``credentials: 'include'``
(their origins are in ``CORS_ORIGIN_WHITELIST`` / ``CSRF_TRUSTED_ORIGINS``). Guests get 401,
accounts not activated yet 403, and the button stays hidden for both.
"""

from pathlib import Path

from django.http import HttpResponse, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST, require_safe

from . import access, entries, labels, schema

WIDGET_PATH = Path(__file__).resolve().parent / 'widget' / 'robbo-whats-new.js'
WIDGET_MAX_AGE = 600


def _lang(request):
    code = (request.GET.get('lang') or '').lower().split('-')[0]
    return code if code in schema.LANGS else labels.current_lang()


def _denied(user):
    if not user.is_authenticated:
        return JsonResponse({'error': 'authentication required'}, status=401)
    return JsonResponse({'error': 'account not activated'}, status=403)


@never_cache
@require_GET
def status(request):
    if not access.can_view(request.user):
        return _denied(request.user)
    return JsonResponse(entries.status(request.user, _lang(request)))


@never_cache
@require_GET
def panel(request):
    if not access.can_view(request.user):
        return _denied(request.user)
    return JsonResponse(entries.panel(request.user, _lang(request)))


@never_cache
@require_POST
def mark_read(request):
    if not access.can_view(request.user):
        return _denied(request.user)
    entries.mark_read(request.user, entries.visible_releases(request.user))
    return JsonResponse({'unread': 0})


@require_safe
def widget(request):
    """The header button script; short cache so a new image reaches MFEs without a rebuild."""
    response = HttpResponse(WIDGET_PATH.read_text(encoding='utf-8'), content_type='text/javascript; charset=utf-8')
    response['Cache-Control'] = f'public, max-age={WIDGET_MAX_AGE}'
    return response
