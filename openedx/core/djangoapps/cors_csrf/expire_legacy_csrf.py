# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (openedx-platform fork).
# See NOTICE at repository root.

"""
Expire host-only legacy csrftoken cookies after CSRF_COOKIE_DOMAIN migration.

When CSRF_COOKIE_DOMAIN moves from host-only to ``.{LMS_HOST}``, browsers may
keep both cookies. Django can then receive the stale host-only value on
cross-site MFE iframe POSTs. This middleware deletes only the host-only cookie
(``domain=LMS_HOST``) on every response and leaves the domain-scoped cookie intact.
"""

from django.conf import settings
from django.utils.deprecation import MiddlewareMixin


class ExpireLegacyCsrfCookieMiddleware(MiddlewareMixin):
    """Delete host-only csrftoken; do not touch Domain=.{LMS_HOST} cookie."""

    def process_response(self, request, response):
        legacy_domain = getattr(settings, "ROBBO_LEGACY_CSRF_COOKIE_DOMAIN", None)
        if not legacy_domain:
            csrf_domain = getattr(settings, "CSRF_COOKIE_DOMAIN", None) or ""
            if csrf_domain.startswith("."):
                legacy_domain = csrf_domain[1:]
            else:
                legacy_domain = getattr(settings, "SITE_NAME", None)
        if legacy_domain:
            response.delete_cookie(
                settings.CSRF_COOKIE_NAME,
                domain=legacy_domain,
                path=getattr(settings, "CSRF_COOKIE_PATH", "/") or "/",
            )
        return response
