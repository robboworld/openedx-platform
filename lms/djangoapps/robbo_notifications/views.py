# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution. See NOTICE at repository root.
"""The notifications header button script (``widget/robbo-notifications.js``)."""

from pathlib import Path

from django.http import HttpResponse
from django.views.decorators.http import require_safe

WIDGET_PATH = Path(__file__).resolve().parent / 'widget' / 'robbo-notifications.js'
WIDGET_MAX_AGE = 600


@require_safe
def widget(request):
    """Short cache, as for «Что нового»: a new image reaches MFEs without rebuilding them."""
    response = HttpResponse(WIDGET_PATH.read_text(encoding='utf-8'), content_type='text/javascript; charset=utf-8')
    response['Cache-Control'] = f'public, max-age={WIDGET_MAX_AGE}'
    return response
