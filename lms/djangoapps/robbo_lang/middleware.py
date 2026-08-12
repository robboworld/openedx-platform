# Copyright (C) 2024-2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution. See NOTICE at repository root.

"""
Force the platform LANGUAGE_CODE for Robbo LMS.

Overrides stale ``openedx-language-preference`` cookies and browser
Accept-Language so Django translations and anonymous caches stay on the
instance language (typically ``ru`` or ``en`` via Tutor ``LANGUAGE_CODE``).
"""
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin

from openedx.core.djangoapps.lang_pref import helpers as lang_pref_helpers


def _forced_language():
    return getattr(settings, 'ROBBO_FORCED_LANGUAGE', None) or settings.LANGUAGE_CODE


class RobboForceRussianLanguageMiddleware(MiddlewareMixin):
    """
    Keep LMS responses on the platform language regardless of browser cookies.

    Class name kept for Tutor patch compatibility; language comes from
    ``ROBBO_FORCED_LANGUAGE`` or ``LANGUAGE_CODE``.

    Inserted at the start of ``MIDDLEWARE`` so ``process_response`` runs last
    and wins over ``LanguagePreferenceMiddleware``.
    """

    def process_request(self, request):
        request.COOKIES[settings.LANGUAGE_COOKIE_NAME] = _forced_language()

    def process_response(self, request, response):
        lang_pref_helpers.set_language_cookie(request, response, _forced_language())
        return response


# Prefer this name in new patches; alias keeps existing env patches working.
RobboForcePlatformLanguageMiddleware = RobboForceRussianLanguageMiddleware
