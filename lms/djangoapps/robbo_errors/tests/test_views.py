# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (human-readable errors). See NOTICE at repository root.
"""Tests for crashes behind the middleware, the JSON error answer, browser reports and the support page."""

import json
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.test import TestCase, override_settings
from django.urls import reverse

from common.djangoapps.student.tests.factories import TEST_PASSWORD, UserFactory
from lms.djangoapps.robbo_errors.apps import SUPPORT_GROUP
from lms.djangoapps.robbo_errors.models import ErrorIncident

REQUEST_ID = '7f3a29c1-1d2e-4f00-8000-0123456789ab'
LOCMEM = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'robbo-errors-views'}}


@override_settings(ROOT_URLCONF='lms.djangoapps.robbo_errors.tests.urls', CACHES=LOCMEM)
class CrashTest(TestCase):
    """What a user gets, and what the journal keeps, when a view crashes or refuses."""

    def setUp(self):
        super().setUp()
        self.client.raise_request_exception = False

    def test_ajax_crash_gets_the_json_answer_and_is_journaled(self):
        response = self.client.get('/crash', HTTP_X_REQUESTED_WITH='XMLHttpRequest', HTTP_X_REQUEST_ID=REQUEST_ID)
        self.assertEqual(response.status_code, 500)
        body = response.json()
        self.assertEqual(body['error_code'], 'SRV-ERROR')
        self.assertEqual(body['incident_id'], REQUEST_ID.replace('-', ''))
        self.assertEqual(body['error'], body['user_message'])
        self.assertEqual(body['audience'], 'learner')
        row = ErrorIncident.objects.get()
        self.assertEqual((row.code, row.short_id, row.status, row.source, row.path), ('SRV-ERROR', '7F3A-29C1', 500, 'lms', '/crash'))
        self.assertIn('ValueError: boom', row.traceback)

    def test_api_crash_gets_json_too(self):
        response = self.client.get('/api/crash', HTTP_ACCEPT='application/json')
        self.assertEqual(response.json()['error_code'], 'SRV-ERROR')
        # Not behind Caddy: the answer carries the number the request got.
        self.assertEqual(response['X-Request-ID'], response.json()['incident_id'])

    def test_page_crash_keeps_the_500_page_and_is_journaled_once(self):
        response = self.client.get('/crash', HTTP_ACCEPT='text/html')
        self.assertEqual(response.content, b'themed 500 page')
        self.assertEqual(ErrorIncident.objects.count(), 1)

    def test_refusals_are_not_crashes(self):
        self.assertEqual(self.client.get('/not-found', HTTP_ACCEPT='application/json').status_code, 404)
        self.assertEqual(self.client.get('/denied', HTTP_ACCEPT='application/json').status_code, 403)
        self.assertFalse(ErrorIncident.objects.exists())

    @patch('lms.djangoapps.robbo_errors.catalog.current_lang', return_value='ru')
    def test_robbo_error(self, _lang):
        user = UserFactory(is_staff=True)
        self.client.login(username=user.username, password=TEST_PASSWORD)
        response = self.client.get('/upload', HTTP_X_REQUEST_ID=REQUEST_ID)
        self.assertEqual(response.status_code, 413)
        body = response.json()
        self.assertEqual(body['error_code'], 'UPLOAD-SIZE')
        self.assertEqual(body['user_message'], 'Файл больше 50 МБ. Уменьшите его или разделите на несколько частей.')
        self.assertEqual(body['developer_message'], '3 files')
        self.assertEqual(body['audience'], 'staff')
        # journal: count — a day counter, not a case.
        self.assertEqual(ErrorIncident.objects.get().incident_id, '')


@override_settings(ROOT_URLCONF='lms.djangoapps.robbo_errors.tests.urls', CACHES=LOCMEM)
class ReportTest(TestCase):
    """Errors only the browser saw."""

    url = '/api/robbo/v1/errors/report'

    def _report(self, data, **kwargs):
        body = data if isinstance(data, str) else json.dumps(data)
        return self.client.post(self.url, body, content_type='text/plain', **kwargs)

    def test_report_is_journaled_without_query_strings(self):
        response = self._report({
            'code': 'NET-OFFLINE', 'incident_id': REQUEST_ID, 'source': 'mfe:learning', 'status': 0,
            'url': 'https://online.robbo.ru/api/courseware/x?token=secret', 'method': 'get',
            'page': 'https://apps.online.robbo.ru/learning/course/x?email=a@b.c#top', 'message': 'Network Error',
        })
        self.assertEqual(response.status_code, 204)
        row = ErrorIncident.objects.get()
        self.assertEqual(
            (row.code, row.short_id, row.source, row.site, row.path, row.page, row.method, row.status),
            ('NET-OFFLINE', '7F3A-29C1', 'mfe:learning', 'online.robbo.ru', '/api/courseware/x', '/learning/course/x', 'GET', 0),
        )
        self.assertEqual(row.developer_message, 'Network Error')

    def test_junk_is_tamed(self):
        response = self._report({'code': '<script>', 'source': 'Robbo MFE!', 'status': 'x', 'audience': 'admin'})
        self.assertEqual(response.status_code, 204)
        row = ErrorIncident.objects.get()
        self.assertEqual((row.code, row.source, row.status, row.audience), ('APP-CRASH', 'browser', None, 'learner'))

    def test_bad_requests(self):
        self.assertEqual(self._report('not json').status_code, 400)
        self.assertEqual(self._report('[1, 2]').status_code, 400)
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertEqual(self._report({'code': 'APP-CRASH', 'message': 'x' * 9000}).status_code, 204)
        self.assertFalse(ErrorIncident.objects.exists())  # too large: ignored


@override_settings(ROOT_URLCONF='lms.djangoapps.robbo_errors.tests.urls', CACHES=LOCMEM)
class SupportPageTest(TestCase):
    """The support page: only for the «Поддержка» group (and superusers), found by the screen's code."""

    def setUp(self):
        super().setUp()
        self.learner = UserFactory(username='claude-learner')
        self.row = ErrorIncident.objects.create(
            code='SRV-ERROR', incident_id=REQUEST_ID.replace('-', ''), source='lms', status=500,
            user=self.learner, path='/api/x', traceback='Traceback…',
        )
        self.support = UserFactory()
        self.support.groups.add(Group.objects.get_or_create(name=SUPPORT_GROUP)[0])
        from django.contrib.auth.models import Permission  # pylint: disable=import-outside-toplevel
        Group.objects.get(name=SUPPORT_GROUP).permissions.add(
            Permission.objects.get(content_type__app_label='robbo_errors', codename='view_errorincident'),
        )

    def _get(self, user, url, **params):
        self.client.login(username=user.username, password=TEST_PASSWORD)
        return self.client.get(url, params)

    def test_hidden_from_everyone_else(self):
        self.assertEqual(self.client.get(reverse('robbo_errors:lookup')).status_code, 302)
        self.assertEqual(self._get(self.learner, reverse('robbo_errors:lookup')).status_code, 404)
        self.assertEqual(self._get(self.learner, reverse('robbo_errors:incident', args=[self.row.pk])).status_code, 404)

    def test_summary_and_reference(self):
        response = self._get(self.support, reverse('robbo_errors:lookup'))
        self.assertContains(response, 'Сводка по видам ошибок')
        self.assertContains(response, 'Справочник видов')
        self.assertContains(response, 'UPLOAD-SIZE')

    def test_search_by_the_line_from_the_screen(self):
        for query in ('Код: SRV-ERROR · 7F3A-29C1', '7f3a29c1', 'claude-learner', 'SRV-ERROR'):
            with self.subTest(query=query):
                response = self._get(self.support, reverse('robbo_errors:lookup'), q=query)
                self.assertContains(response, reverse('robbo_errors:incident', args=[self.row.pk]))
        self.assertContains(self._get(self.support, reverse('robbo_errors:lookup'), q='0000-0000'), 'Ничего не нашлось')

    def test_incident_card(self):
        response = self._get(self.support, reverse('robbo_errors:incident', args=[self.row.pk]))
        self.assertContains(response, 'Не получилось выполнить действие')
        self.assertContains(response, 'Трассировка')
        self.assertContains(response, 'claude-learner')
