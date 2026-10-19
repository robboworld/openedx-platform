# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (human-readable errors). See NOTICE at repository root.
"""
The error page of the LMS and Studio (docs/human-errors.md §1 and §7): the title and message of the
code, one action, the code with the incident number and a «Copy» button, whom to turn to.

``robbo_errors/error_page.html`` exists twice: the LMS one inherits ``main.html``, the Studio one
``base.html``; both include ``common/templates/robbo_errors/_error_block.html``. If the page itself
cannot be rendered (the error may be the database or the templates), a plain page without the site's
header is returned instead, so the user never gets a bare "Server Error".
"""

import logging
from html import escape
from urllib.parse import quote

from django.http import HttpResponse, JsonResponse

from common.djangoapps.edxmako.shortcuts import render_to_string
from lms.djangoapps.robbo_changelog.labels import current_lang

from . import catalog
from .ids import request_incident_id, short_id
from .responses import LEARNER, STAFF, audience, error_payload, journal_request, wants_json

log = logging.getLogger(__name__)

TEMPLATE = 'robbo_errors/error_page.html'

# What the page offers first. A page answering a POST must not reload (it would post again).
ACTIONS = {
    'SESSION-EXPIRED': 'login',
    'NOT-FOUND': 'home',
    'ACCESS-DENIED': 'home',
    'PAGE-STALE': 'back',
    'BAD-INPUT': 'back',
    'TOO-MANY': 'back',
    'UPLOAD-SIZE': 'back',
}


def _audience(request):
    try:
        return audience(getattr(request, 'user', None))
    except Exception:  # pylint: disable=broad-except
        return LEARNER  # the database may be the error


def page_context(request, code, **params):
    """Everything ``_error_block.html`` shows, in the user's language."""
    lang = current_lang()
    text = catalog.describe(code, lang, **params)
    action = ACTIONS.get(code, 'reload')
    help_key = 'help_staff' if _audience(request) == STAFF else 'help_learner'
    help_before, help_link, help_after = catalog.split_link(catalog.ui_text(help_key, lang))
    return {
        'robbo_error': {
            'lang': lang,
            'code': code,
            'short_id': short_id(request_incident_id(request)),
            'title': text.title,
            'message': text.message,
            'action': action,
            'action_label': catalog.ui_text(action, lang),  # the catalog's ui has a label per action
            'home_label': catalog.ui_text('home', lang),
            'login_url': f'/login?next={quote(request.get_full_path(), safe="")}',
            'code_label': catalog.ui_text('code', lang),
            'copy_label': catalog.ui_text('copy', lang),
            'copied_label': catalog.ui_text('copied', lang),
            'help_before': help_before,
            'help_link': help_link,
            'help_after': help_after,
            'support_url': catalog.support_url(),
        },
    }


def plain_page(context):
    """The page without templates or the site's header, for when rendering the real one failed."""
    e = {key: escape(str(value)) for key, value in context['robbo_error'].items()}
    return (
        f'<!doctype html><html lang="{e["lang"]}"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width, initial-scale=1"><title>{e["title"]}</title></head>'
        f'<body style="font-family: Helvetica, Arial, sans-serif; color: #383838; max-width: 34rem; margin: 3rem auto;'
        f' padding: 0 1rem;"><h1>{e["title"]}</h1><p>{e["message"]}</p><p><a href="/">{e["home_label"]}</a></p>'
        f'<p>{e["code_label"]}: {e["code"]} · {e["short_id"]}</p>'
        f'<p>{e["help_before"]}<a href="{e["support_url"]}">{e["help_link"]}</a>{e["help_after"]}</p></body></html>'
    )


def error_answer(request, code, status, *, journal=True, developer_message='', **params):
    """
    Answer ``request`` with error ``code``: JSON (docs/human-errors.md §4) for AJAX and API calls,
    the error page otherwise. ``journal=False`` when the error is already in the journal (crashes,
    written by the middleware) or not worth a counter (404s, mostly bots).
    """
    if journal:
        try:
            journal_request(request, code, status, developer_message=developer_message)
        except Exception:  # pylint: disable=broad-except
            log.exception('robbo_errors: could not journal %s', code)
    if wants_json(request):
        try:
            payload = error_payload(request, code, developer_message=developer_message, **params)
        except Exception:  # pylint: disable=broad-except
            log.exception('robbo_errors: could not build the error answer')
            text = catalog.describe(code, **params)
            payload = {'error_code': code, 'user_title': text.title, 'user_message': text.message,
                       'incident_id': request_incident_id(request), 'error': text.message}
        return JsonResponse(payload, status=status)
    context = page_context(request, code, **params)
    try:
        html = render_to_string(TEMPLATE, context, request=request)
    except Exception:  # pylint: disable=broad-except
        log.exception('robbo_errors: could not render the error page for %s', code)
        html = plain_page(context)
    return HttpResponse(html, status=status)
