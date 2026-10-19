# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (human-readable errors). See NOTICE at repository root.
"""Tests for writing to the error journal: merging repeats, day counters, the cap, purging."""

from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from common.djangoapps.student.tests.factories import UserFactory
from lms.djangoapps.robbo_errors.journal import record
from lms.djangoapps.robbo_errors.models import ErrorIncident

LOCMEM = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'robbo-errors'}}
NUMBER_1 = '7f3a29c11d2e4f0080000123456789ab'
NUMBER_2 = '0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e'


@override_settings(CACHES=LOCMEM)
class JournalTest(TestCase):
    """One user's errors and everybody's counters."""

    def setUp(self):
        super().setUp()
        self.user = UserFactory()
        from django.core.cache import cache  # pylint: disable=import-outside-toplevel
        cache.clear()

    def _case(self, number, **kwargs):
        fields = {'source': 'lms', 'site': 'online.robbo.ru', 'path': '/api/x', 'user': self.user, 'status': 500}
        fields.update(kwargs)
        return record('SRV-ERROR', incident_id=number, **fields)

    def test_case_is_written(self):
        row = self._case(NUMBER_1, traceback='Traceback…')
        self.assertEqual((row.code, row.short_id, row.user, row.count), ('SRV-ERROR', '7F3A-29C1', self.user, 1))
        self.assertEqual(row.traceback, 'Traceback…')

    def test_repeats_within_a_minute_are_merged_and_stay_searchable(self):
        first = self._case(NUMBER_1)
        self._case(NUMBER_2)
        self.assertEqual(ErrorIncident.objects.count(), 1)
        first.refresh_from_db()
        self.assertEqual(first.count, 2)
        self.assertEqual(first.merged_ids, '0b1c2d3e')

    def test_another_path_or_an_older_error_is_a_new_row(self):
        first = self._case(NUMBER_1)
        self._case(NUMBER_2, path='/api/y')
        ErrorIncident.objects.filter(pk=first.pk).update(last_seen=timezone.now() - timedelta(minutes=2))
        self._case(NUMBER_2)
        self.assertEqual(ErrorIncident.objects.count(), 3)

    def test_count_codes_keep_one_counter_a_day(self):
        for number in (NUMBER_1, NUMBER_2):
            record('UPLOAD-SIZE', incident_id=number, source='lms', site='online.robbo.ru', path='/upload',
                   user=self.user, status=413)
        row = ErrorIncident.objects.get()
        self.assertEqual((row.code, row.count, row.incident_id, row.user, row.path), ('UPLOAD-SIZE', 2, '', None, ''))

    def test_case_without_a_number_gets_one(self):
        row = record('APP-CRASH', source='mfe:learning', user=None)
        self.assertEqual(len(row.incident_id), 32)
        self.assertIsNone(row.user)

    @override_settings(ROBBO_ERRORS_MAX_PER_MINUTE=2)
    def test_cap(self):
        rows = [self._case(NUMBER_1, path=f'/api/{n}') for n in range(3)]
        self.assertIsNone(rows[2])
        self.assertEqual(ErrorIncident.objects.count(), 2)

    def test_long_values_are_clipped(self):
        row = self._case(NUMBER_1, path='/' + 'x' * 1000, user_agent='u' * 1000)
        self.assertEqual((len(row.path), len(row.user_agent)), (512, 255))

    @override_settings(ROBBO_ERRORS_RETENTION_DAYS=90)
    def test_old_rows_are_purged(self):
        old = self._case(NUMBER_1)
        ErrorIncident.objects.filter(pk=old.pk).update(last_seen=timezone.now() - timedelta(days=91))
        with patch('lms.djangoapps.robbo_errors.journal.random.randrange', return_value=0):
            self._case(NUMBER_2, path='/api/new')
        self.assertEqual(list(ErrorIncident.objects.values_list('path', flat=True)), ['/api/new'])
