# Copyright (C) 2024-2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution. See NOTICE at repository root.

"""
Force the platform LANGUAGE_CODE for Robbo LMS.

Overrides stale ``openedx-language-preference`` cookies and browser
Accept-Language so Django translations and anonymous caches stay on the
instance language (``en`` on ``robbo/courses``, ``ru`` on ``robbo/online``).
"""
from django.conf import settings
from django.utils import translation
from django.utils.deprecation import MiddlewareMixin

from openedx.core.djangoapps.lang_pref import LANGUAGE_HEADER
from openedx.core.djangoapps.lang_pref import helpers as lang_pref_helpers


def _forced_language():
    return getattr(settings, 'ROBBO_FORCED_LANGUAGE', None) or settings.LANGUAGE_CODE


class RobboForceRussianLanguageMiddleware(MiddlewareMixin):
    """
    Keep LMS/CMS responses on the platform language regardless of browser cookies.

    Class name kept for Tutor patch compatibility; language comes from
    ``ROBBO_FORCED_LANGUAGE`` or ``LANGUAGE_CODE`` (English on courses).

    Appended to ``MIDDLEWARE`` so ``process_request`` runs after
    ``LocaleMiddleware`` and ``DarkLangMiddleware`` (released langs may be
    English-only). ``process_response`` still runs last and wins on cookies.
    """

    def process_request(self, request):
        lang = _forced_language()
        request.COOKIES[settings.LANGUAGE_COOKIE_NAME] = lang
        request.META[LANGUAGE_HEADER] = lang
        translation.activate(lang)

    def process_response(self, request, response):
        lang_pref_helpers.set_language_cookie(request, response, _forced_language())
        return response


# Prefer this name in new patches; alias keeps existing env patches working.
RobboForcePlatformLanguageMiddleware = RobboForceRussianLanguageMiddleware
