# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (human-readable errors). See NOTICE at repository root.
"""Tests for the error pages of the LMS (handler400/403/404/500, CSRF failure)."""

import json
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase, override_settings
from django_ratelimit.exceptions import Ratelimited

from lms.djangoapps.robbo_errors import handlers
from lms.djangoapps.robbo_errors.models import ErrorIncident

REQUEST_ID = '7f3a29c1-1d2e-4f00-8000-0123456789ab'
LOCMEM = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'robbo-errors-pages'}}


@override_settings(CACHES=LOCMEM)
@patch('lms.djangoapps.robbo_errors.pages.current_lang', return_value='ru')
@patch('lms.djangoapps.robbo_errors.catalog.current_lang', return_value='ru')
class ErrorPagesTest(TestCase):
    """What the browser and AJAX get from Django's error handlers."""

    def _request(self, path='/courses/nope', ajax=False, method='get'):
        headers = {'HTTP_X_REQUEST_ID': REQUEST_ID}
        if ajax:
            headers['HTTP_X_REQUESTED_WITH'] = 'XMLHttpRequest'
        else:
            headers['HTTP_ACCEPT'] = 'text/html'
        request = getattr(RequestFactory(), method)(path, **headers)
        request.user = AnonymousUser()
        return request

    def test_404_page(self, *_):
        response = handlers.handler404(self._request())
        self.assertEqual(response.status_code, 404)
        html = response.content.decode()
        self.assertIn('Страница не найдена', html)
        self.assertIn('NOT-FOUND · 7F3A-29C1', html)
        self.assertIn('Покажите это сообщение преподавателю или', html)
        self.assertIn('https://support.robbo.world/', html)
        self.assertFalse(ErrorIncident.objects.exists())  # 404s are not counted

    def test_404_ajax(self, *_):
        response = handlers.handler404(self._request(ajax=True))
        self.assertEqual(response.status_code, 404)
        body = json.loads(response.content)
        self.assertEqual(body['error_code'], 'NOT-FOUND')
        self.assertEqual(body['incident_id'], REQUEST_ID.replace('-', ''))

    def test_rate_limit_is_429(self, *_):
        response = handlers.handler403(self._request(method='post'), Ratelimited())
        self.assertEqual(response.status_code, 429)
        self.assertIn('Слишком много попыток', response.content.decode())

    def test_403(self, *_):
        response = handlers.handler403(self._request(ajax=True), None)
        self.assertEqual((response.status_code, json.loads(response.content)['error_code']), (403, 'ACCESS-DENIED'))
        self.assertEqual(ErrorIncident.objects.get().code, 'ACCESS-DENIED')  # a day counter

    def test_csrf_failure(self, *_):
        response = handlers.csrf_failure(self._request(method='post'), reason='CSRF token missing.')
        self.assertEqual(response.status_code, 403)
        html = response.content.decode()
        self.assertIn('Страница устарела', html)
        self.assertIn('history.back()', html)  # a POST must not be reloaded
        self.assertEqual(ErrorIncident.objects.get().code, 'PAGE-STALE')  # a day counter, no details

    def test_400_counts(self, *_):
        handlers.handler400(self._request(ajax=True), ValueError('bad'))
        handlers.handler400(self._request(ajax=True), ValueError('bad'))
        self.assertEqual(ErrorIncident.objects.get().count, 2)

    def test_500_is_not_journaled_twice(self, *_):
        response = handlers.handler500(self._request())
        self.assertEqual(response.status_code, 500)
        self.assertIn('SRV-ERROR · 7F3A-29C1', response.content.decode())
        self.assertFalse(ErrorIncident.objects.exists())  # the middleware journals the crash

    def test_plain_page_when_rendering_fails(self, *_):
        with patch('lms.djangoapps.robbo_errors.pages.render_to_string', side_effect=RuntimeError('no db')):
            response = handlers.handler500(self._request())
        html = response.content.decode()
        self.assertEqual(response.status_code, 500)
        self.assertIn('<h1>Не получилось выполнить действие</h1>', html)
        self.assertIn('SRV-ERROR · 7F3A-29C1', html)
