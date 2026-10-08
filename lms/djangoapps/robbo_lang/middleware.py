# Copyright (C) 2024-2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution. See NOTICE at repository root.

"""
Force the platform LANGUAGE_CODE for Robbo LMS.

Overrides stale ``openedx-language-preference`` cookies and browser
Accept-Language so Django translations and anonymous caches stay on the
instance language (``en`` on ``robbo/courses``, ``ru`` on ``robbo/online``).

With ``ROBBO_LANGUAGE_FROM_ACCOUNT`` (``robbo/courses``) a signed-in user's requests — LMS, Studio and the
MFEs through the language cookie — use the language saved in Account settings («Site language»);
anonymous visitors keep the platform language.
"""
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import translation
from django.utils.deprecation import MiddlewareMixin
from edx_rest_framework_extensions.auth.jwt.cookies import jwt_cookie_header_payload_name, jwt_cookie_signature_name
from edx_rest_framework_extensions.auth.jwt.decoder import jwt_decode_handler

from openedx.core.djangoapps.lang_pref import LANGUAGE_HEADER, LANGUAGE_KEY
from openedx.core.djangoapps.lang_pref import helpers as lang_pref_helpers
from openedx.core.djangoapps.lang_pref.api import released_languages
from openedx.core.djangoapps.user_api.models import UserPreference

log = logging.getLogger(__name__)


def _forced_language():
    return getattr(settings, 'ROBBO_FORCED_LANGUAGE', None) or settings.LANGUAGE_CODE


def _jwt_from_request(request):
    """The JWT of the request: the Authorization header, or the JWT cookies the MFEs send."""
    header = request.META.get('HTTP_AUTHORIZATION', '')
    if header.startswith('JWT '):
        return header[4:]
    header_payload = request.COOKIES.get(jwt_cookie_header_payload_name())
    signature = request.COOKIES.get(jwt_cookie_signature_name())
    return f'{header_payload}.{signature}' if header_payload and signature else None


def _request_user(request):
    """
    Signed-in user of the request. MFE API calls authenticate with the JWT cookies in the view (DRF) —
    JwtAuthCookieMiddleware builds the header only in process_view, after this middleware — so the JWT
    is verified here as well.
    """
    user = getattr(request, 'user', None)
    if user is not None and user.is_authenticated:
        return user
    token = _jwt_from_request(request)
    if not token:
        return None
    try:
        username = jwt_decode_handler(token).get('preferred_username')
    except Exception:  # pylint: disable=broad-except
        log.debug('robbo_lang: JWT not usable for the language choice', exc_info=True)
        return None
    return get_user_model().objects.filter(username=username, is_active=True).first() if username else None


def _request_language(request):
    """The platform language; on courses a signed-in user's language from Account settings."""
    if getattr(settings, 'ROBBO_LANGUAGE_FROM_ACCOUNT', False):
        user = _request_user(request)
        if user is not None:
            preferred = UserPreference.get_value(user, LANGUAGE_KEY)
            if preferred and preferred in {language.code for language in released_languages()}:
                return preferred
    return _forced_language()


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
        lang = _request_language(request)
        request.robbo_language = lang
        request.COOKIES[settings.LANGUAGE_COOKIE_NAME] = lang
        request.META[LANGUAGE_HEADER] = lang
        translation.activate(lang)

    def process_response(self, request, response):
        lang = getattr(request, 'robbo_language', None) or _forced_language()
        lang_pref_helpers.set_language_cookie(request, response, lang)
        return response


# Prefer this name in new patches; alias keeps existing env patches working.
RobboForcePlatformLanguageMiddleware = RobboForceRussianLanguageMiddleware
