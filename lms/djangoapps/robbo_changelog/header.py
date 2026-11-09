# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (site changelog). See NOTICE at repository root.
"""
First state of the «Что нового» header button on LMS and Studio Mako pages.

The header renders it into ``data-initial`` (the ``status`` API answer), so the widget shows the
button together with the page instead of after a request. MFEs have no server render and keep the request.
"""

import json
import logging

from . import access, entries

log = logging.getLogger(__name__)


def initial_json(user, lang):
    """``status`` for ``user`` as JSON; empty when the user may not see it or on any error (the widget asks the API)."""
    if not access.can_view(user):
        return ''
    try:
        return json.dumps(entries.status(user, lang), ensure_ascii=False)
    except Exception:  # pylint: disable=broad-except
        log.exception('robbo_changelog: header status for %s failed', user.id)
        return ''
