# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (human-readable errors). See NOTICE at repository root.
"""Tests for the catalog of error codes and incident numbers."""

import ddt
from django.test import SimpleTestCase

from lms.djangoapps.robbo_errors import catalog
from lms.djangoapps.robbo_errors.ids import normalize, parse_query, short_id


class CatalogTest(SimpleTestCase):
    """catalog.yaml loads, and every code has what the pages and the MFE copy rely on."""

    def test_every_code_is_complete(self):
        for code, kind in catalog.codes().items():
            with self.subTest(code=code):
                self.assertRegex(code, r'^[A-Z]+(-[A-Z]+)+$')
                self.assertIn(kind.journal, catalog.JOURNAL_MODES)
                self.assertTrue(kind.support, 'support staff need to know what to answer')
                for lang in catalog.LANGUAGES:
                    self.assertTrue(kind.title[lang])
                    # A message must be shown even when its parameters are unknown.
                    self.assertNotIn('{', catalog.describe(code, lang=lang).message)

    def test_status_codes_exist(self):
        for status, code in catalog.STATUS_CODES.items():
            with self.subTest(status=status):
                self.assertIsNotNone(catalog.get(code))
        self.assertEqual(catalog.code_for_status(500), 'SRV-ERROR')
        self.assertEqual(catalog.code_for_status(418), 'BAD-INPUT')

    def test_message_parameters(self):
        self.assertEqual(
            catalog.describe('UPLOAD-SIZE', lang='ru', limit=50).message,
            'Файл больше 50 МБ. Уменьшите его или разделите на несколько частей.',
        )
        self.assertEqual(
            catalog.describe('UPLOAD-SIZE', lang='en').message,
            'The file is too large. Make it smaller or split it into parts.',
        )

    def test_unknown_code_gets_the_server_error_text(self):
        self.assertEqual(catalog.describe('NO-SUCH-CODE', lang='ru'), catalog.describe('SRV-ERROR', lang='ru'))

    def test_ui_texts(self):
        self.assertEqual(catalog.ui_text('code', lang='en'), 'Code')
        self.assertTrue(catalog.support_url().startswith('https://'))


@ddt.ddt
class IdsTest(SimpleTestCase):
    """Incident numbers: from Caddy's request UUID to the screen and back from the support search."""

    @ddt.data(
        ('7f3a29c1-1d2e-4f00-8000-0123456789ab', '7f3a29c11d2e4f0080000123456789ab'),
        ('7F3A29C1', '7f3a29c1'),
        ('', ''),
        ('not-a-uuid', ''),
        ('7f3a', ''),
    )
    @ddt.unpack
    def test_normalize(self, raw, expected):
        self.assertEqual(normalize(raw), expected)

    def test_short_id(self):
        self.assertEqual(short_id('7f3a29c11d2e'), '7F3A-29C1')
        self.assertEqual(short_id(''), '')

    @ddt.data(
        ('Код: UPLOAD-SIZE · 7F3A-29C1', ('7f3a29c1', 'UPLOAD-SIZE')),
        ('7f3a29c1', ('7f3a29c1', None)),
        ('7f3a-29c1', ('7f3a29c1', None)),
        ('7f3a29c1-1d2e-4f00-8000-0123456789ab', ('7f3a29c1', None)),
        ('ACCESS-DENIED', (None, 'ACCESS-DENIED')),
        ('BAD-INPUT · FACE-B00C', ('faceb00c', 'BAD-INPUT')),
        # Looks like a code: the support page searches logins when the catalog has no such code.
        ('claude-learner', (None, 'CLAUDE-LEARNER')),
        ('learner42', (None, None)),
    )
    @ddt.unpack
    def test_parse_query(self, query, expected):
        self.assertEqual(parse_query(query), expected)
