# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (certificate signatures). See NOTICE at repository root.
"""Tests for xmodule.contentstore.robbo_signature_assets."""

from unittest import TestCase
from unittest.mock import Mock

from opaque_keys.edx.keys import CourseKey

from xmodule.contentstore.robbo_signature_assets import relink_certificate_signatures, signature_asset_key

SOURCE = CourseKey.from_string('course-v1:Robbo+SRC+2025')
COPY = CourseKey.from_string('course-v1:Robbo+COPY+2026')
SOURCE_PATH = '/asset-v1:Robbo+SRC+2025+type@asset+block@sig.png'
COPY_PATH = '/asset-v1:Robbo+COPY+2026+type@asset+block@sig.png'


def certificates(*paths):
    return {'certificates': [{'id': 1, 'signatories': [{'name': 'A', 'signature_image_path': p} for p in paths]}]}


def content_store(*existing):
    """Contentstore mock that finds only the given asset keys."""
    store = Mock()
    store.find.side_effect = lambda key, throw_on_not_found=True: object() if key in existing else None
    return store


class RelinkCertificateSignaturesTest(TestCase):
    """Signature paths copied from another course point at the course's own file."""

    def test_foreign_path_points_at_own_copy(self):
        own = COPY.make_asset_key('asset', 'sig.png')
        original = certificates(SOURCE_PATH)
        updated = relink_certificate_signatures(original, COPY, content_store(own))
        assert updated['certificates'][0]['signatories'][0]['signature_image_path'] == COPY_PATH
        # the course field value is not changed in place
        assert original['certificates'][0]['signatories'][0]['signature_image_path'] == SOURCE_PATH

    def test_no_own_copy_keeps_path(self):
        assert relink_certificate_signatures(certificates(SOURCE_PATH), COPY, content_store()) is None

    def test_own_path_empty_and_invalid_are_left_alone(self):
        own = COPY.make_asset_key('asset', 'sig.png')
        assert relink_certificate_signatures(
            certificates(COPY_PATH, '', 'not an asset path'), COPY, content_store(own),
        ) is None

    def test_no_certificates(self):
        assert relink_certificate_signatures(None, COPY, content_store()) is None
        assert relink_certificate_signatures({}, COPY, content_store()) is None

    def test_signature_asset_key(self):
        assert signature_asset_key(SOURCE_PATH) == SOURCE.make_asset_key('asset', 'sig.png')
        assert signature_asset_key('  ') is None
        assert signature_asset_key('not an asset path') is None
