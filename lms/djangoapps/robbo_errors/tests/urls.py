# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (human-readable errors). See NOTICE at repository root.
"""A test URLconf: views that crash or refuse, behind the real middleware."""

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.urls import include, path

from lms.djangoapps.robbo_errors.responses import robbo_error


def crash(request):
    raise ValueError('boom')


def not_found(request):
    raise Http404


def denied(request):
    raise PermissionDenied


def upload(request):
    return robbo_error(request, 'UPLOAD-SIZE', developer_message='3 files', limit=50)


def handler500(request):  # pylint: disable=unused-argument
    return HttpResponse('themed 500 page', status=500)


urlpatterns = [
    path('crash', crash),
    path('api/crash', crash),
    path('not-found', not_found),
    path('denied', denied),
    path('upload', upload),
    path('', include('lms.djangoapps.robbo_errors.urls', namespace='robbo_errors')),
    # The support page borrows the admin look, which links to the admin index.
    path('admin/', admin.site.urls),
]
