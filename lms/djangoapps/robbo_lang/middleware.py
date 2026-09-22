# Copyright (C) 2024-2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution. See NOTICE at repository root.

"""
Force Russian locale for Robbo LMS.

Overrides stale ``openedx-language-preference`` cookies and browser
Accept-Language so Django translations and anonymous caches stay Russian.
"""
from django.conf import settings
from django.utils import translation
from django.utils.deprecation import MiddlewareMixin

from openedx.core.djangoapps.lang_pref import LANGUAGE_HEADER
from openedx.core.djangoapps.lang_pref import helpers as lang_pref_helpers

ROBBO_FORCED_LANGUAGE = 'ru'


class RobboForceRussianLanguageMiddleware(MiddlewareMixin):
    """
    Keep LMS/CMS responses in Russian regardless of browser language cookies.

    Appended to ``MIDDLEWARE`` so ``process_request`` runs after
    ``LocaleMiddleware`` and ``DarkLangMiddleware`` (released langs may be
    English-only). ``process_response`` still runs last and wins on cookies.
    """

    def process_request(self, request):
        request.COOKIES[settings.LANGUAGE_COOKIE_NAME] = ROBBO_FORCED_LANGUAGE
        request.META[LANGUAGE_HEADER] = ROBBO_FORCED_LANGUAGE
        translation.activate(ROBBO_FORCED_LANGUAGE)

    def process_response(self, request, response):
        lang_pref_helpers.set_language_cookie(request, response, ROBBO_FORCED_LANGUAGE)
        return response
