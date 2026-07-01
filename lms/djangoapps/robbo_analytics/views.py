# Copyright (C) 2024-2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of the Robbo Open edX distribution. See NOTICE at repository root.

"""
Robbo global analytics views.
"""
from __future__ import annotations

import logging
from functools import wraps

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET

from common.djangoapps.edxmako.shortcuts import render_to_response
from lms.djangoapps.robbo_analytics.access import can_access_robbo_global_analytics
from lms.djangoapps.robbo_analytics.services import build_analytics_page_context
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers

log = logging.getLogger(__name__)


def _get_lms_analytics_url() -> str:
    """
    Public LMS URL for the analytics page (stable for MFE menus).
    """
    lms_root = (
        configuration_helpers.get_value('LMS_ROOT_URL')
        or settings.LMS_ROOT_URL
        or ''
    ).rstrip('/')
    if not lms_root:
        return '/robbo/analytics/'
    return f'{lms_root}/robbo/analytics/'


def robbo_analytics_required(view_func):
    """
    Require login and Robbo analytics access for the wrapped view.
    """
    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not can_access_robbo_global_analytics(request.user):
            return HttpResponseForbidden(_("You do not have permission to access analytics."))
        return view_func(request, *args, **kwargs)

    return wrapper


@robbo_analytics_required
def global_enrollments(request):
    """
    Platform analytics: summary, filters, and per-course participant metrics.
    """
    try:
        context = build_analytics_page_context(request.GET.get('filter'))
        return render_to_response(
            'robbo_analytics/global_enrollments.html',
            context,
            request=request,
        )
    except Exception:  # pylint: disable=broad-except
        log.exception('Robbo analytics page failed')
        raise


@require_GET
def analytics_menu(request):
    """
    JSON payload for MFE/LMS menus: whether to show Analytics and where it links.
    """
    if not request.user.is_authenticated:
        return JsonResponse({'can_access': False, 'url': None}, status=401)

    can_access = can_access_robbo_global_analytics(request.user)
    return JsonResponse({
        'can_access': can_access,
        'url': _get_lms_analytics_url() if can_access else None,
    })
