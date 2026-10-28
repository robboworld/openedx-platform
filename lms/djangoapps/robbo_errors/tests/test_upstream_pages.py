# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (human-readable errors). See NOTICE at repository root.
"""Tests for the error pages that views render themselves (upstream_pages.py) and their journal."""

from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.db import transaction
from django.test import RequestFactory, TestCase, override_settings

from lms.djangoapps.robbo_errors.models import ErrorIncident
from lms.djangoapps.robbo_errors.upstream_pages import error_for, run_deferred_journal

REQUEST_ID = '7f3a29c1-1d2e-4f00-8000-0123456789ab'
LOCMEM = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'robbo-errors-upstream'}}


@override_settings(CACHES=LOCMEM)
@patch('lms.djangoapps.robbo_errors.upstream_pages.current_lang', return_value='ru')
@patch('lms.djangoapps.robbo_errors.pages.current_lang', return_value='ru')
@patch('lms.djangoapps.robbo_errors.catalog.current_lang', return_value='ru')
class UpstreamPagesTest(TestCase):
    """The texts of a page and the one case it journals."""

    def _request(self):
        request = RequestFactory().get('/email_confirm/key', HTTP_X_REQUEST_ID=REQUEST_ID)
        request.user = AnonymousUser()
        return request

    def test_texts_and_action_link(self, *_):
        error = error_for('email_change_failed', self._request(), email='new@example.com')
        self.assertEqual(error['code'], 'SRV-ERROR')
        self.assertEqual(error['short_id'], '7F3A-29C1')
        self.assertEqual(error['title'], 'Не удалось сменить почту')
        self.assertIn('new@example.com', error['message'])
        self.assertEqual((error['action'], error['action_label']), ('link', 'Открыть настройки учётной записи'))

    def test_block_action_stays(self, *_):
        error = error_for('courseware_error', self._request())
        self.assertEqual(error['action'], 'reload')
        self.assertNotIn('action_url', error)

    def test_journal_waits_for_the_rollback_and_writes_one_case(self, *_):
        request = self._request()
        try:
            with transaction.atomic():
                # a template asks for the page twice: in the title and in the body
                error_for('email_change_failed', request, email='new@example.com')
                error_for('email_change_failed', request, email='new@example.com')
                raise RuntimeError('confirm_email_change rolls back')
        except RuntimeError:
            pass
        self.assertFalse(ErrorIncident.objects.exists())
        run_deferred_journal(request)
        row = ErrorIncident.objects.get()
        self.assertEqual((row.code, row.status, row.developer_message), ('SRV-ERROR', 500, 'email_change_failed'))
        run_deferred_journal(request)  # the middleware may call it again: nothing left
        self.assertEqual(ErrorIncident.objects.count(), 1)

    def test_pages_without_journal(self, *_):
        request = self._request()
        error_for('email_key', request)
        run_deferred_journal(request)
        self.assertFalse(ErrorIncident.objects.exists())
