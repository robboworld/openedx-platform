# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (site changelog). See NOTICE at repository root.
"""«Что нового» full page: signed-in users with an activated account, entries filtered by site and role."""

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.views.decorators.http import require_GET

from common.djangoapps.edxmako.shortcuts import render_to_response

from .access import can_view
from .entries import build_page, mark_read


@login_required
@require_GET
def whats_new(request):
    if not can_view(request.user):
        # Not activated yet: the section does not exist for this account (no button either).
        raise Http404
    context = build_page(request.user, request.GET.get('section'), request.GET.get('for'))
    response = render_to_response('robbo_changelog/whats_new.html', context)
    # Unread entries are highlighted on this render, then count as read (as in the header panel).
    mark_read(request.user, context['visible'])
    return response
