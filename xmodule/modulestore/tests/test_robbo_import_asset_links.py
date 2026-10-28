# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (course import). See NOTICE at repository root.
"""Tests for xmodule.modulestore.robbo_import_asset_links."""

import os
import shutil
import tempfile
from unittest import TestCase
from unittest.mock import Mock

from opaque_keys.edx.keys import CourseKey

from xmodule.modulestore.robbo_import_asset_links import ImportAssetLinks

SOURCE = CourseKey.from_string('course-v1:Robbo+SRC+2025')
DEST = CourseKey.from_string('course-v1:Robbo+DEST+2026')
MD5 = '0123456789abcdef0123456789abcdef'


def content_store(*names):
    """Contentstore mock that finds only the given asset names of DEST."""
    existing = {DEST.make_asset_key('asset', name) for name in names}
    store = Mock()
    store.find.side_effect = lambda key, throw_on_not_found=True, as_stream=False: (
        object() if key in existing else None
    )
    return store


class ImportAssetLinksTest(TestCase):
    """Full links to course files lose the old host and, for the course's own files, become /static/."""

    def setUp(self):
        super().setUp()
        self.static_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.static_dir)
        for subpath in ('pic.png', 'img/nested.png', '._pic.png'):
            os.makedirs(os.path.dirname(os.path.join(self.static_dir, subpath)), exist_ok=True)
            with open(os.path.join(self.static_dir, subpath), 'wb') as f:
                f.write(b'x')

    def links(self, store=None):
        return ImportAssetLinks(SOURCE, DEST, static_dir=self.static_dir, content_store=store or content_store())

    def test_own_file_with_host_becomes_static(self):
        links = self.links()
        for url in (
            'https://lms2.robbo.world/asset-v1:Robbo+SRC+2025+type@asset+block@pic.png',
            'https://online.robbo.ru/asset-v1:Robbo+SRC+2025+type@asset+block/pic.png',
            f'http://test.lms.robbo.ru:8000/assets/courseware/v1/{MD5}/asset-v1:Robbo+SRC+2025+type@asset+block/pic.png',
            '//online.robbo.ru/asset-v1:Robbo+DEST+2026+type@asset+block@pic.png',
            f'/assets/courseware/v1/{MD5}/asset-v1:Robbo+SRC+2025+type@asset+block/pic.png',
            '/asset-v1:Robbo+SRC+2025+type@asset+block@pic.png',
        ):
            assert links.rewrite_text(f'<img src="{url}">', to_static=True) == '<img src="/static/pic.png">', url
        assert links.rewritten == 6

    def test_nested_static_file_and_query(self):
        text = 'url(https://lms2.robbo.world/asset-v1:Robbo+SRC+2025+type@asset+block@img_nested.png?v=2)'
        assert self.links().rewrite_text(text, to_static=True) == 'url(/static/img_nested.png?v=2)'

    def test_file_already_in_new_course(self):
        text = '"https://lms2.robbo.world/asset-v1:Robbo+SRC+2025+type@asset+block@old.png"'
        assert self.links(content_store('old.png')).rewrite_text(text, to_static=True) == '"/static/old.png"'

    def test_other_fields_get_new_course_asset_path(self):
        text = 'https://lms2.robbo.world/asset-v1:Robbo+SRC+2025+type@asset+block@pic.png'
        assert self.links().rewrite_text(text, to_static=False) == '/asset-v1:Robbo+DEST+2026+type@asset+block@pic.png'

    def test_missing_and_foreign_files_only_lose_the_host(self):
        links = self.links(content_store('pic.png'))
        text = (
            '<img src="https://lms2.robbo.world/asset-v1:Robbo+SRC+2025+type@asset+block@missing.png">'
            '<img src="https://online.robbo.ru/asset-v1:Robbo+OLD+2024+type@asset+block@pic.png">'
            f'<img src="https://online.robbo.ru/assets/courseware/v1/{MD5}/asset-v1:Robbo+OLD+2024+type@asset+block/pic.png">'
        )
        assert links.rewrite_text(text, to_static=True) == (
            '<img src="/asset-v1:Robbo+SRC+2025+type@asset+block@missing.png">'
            '<img src="/asset-v1:Robbo+OLD+2024+type@asset+block@pic.png">'
            f'<img src="/assets/courseware/v1/{MD5}/asset-v1:Robbo+OLD+2024+type@asset+block/pic.png">'
        )

    def test_hostless_foreign_and_other_links_are_left_alone(self):
        text = (
            '<img src="/asset-v1:Robbo+OLD+2024+type@asset+block@pic.png">'
            '<img src="/static/pic.png"><a href="https://example.com/asset-v1-guide">x</a>'
            '<img src="/asset-v1:Robbo+SRC+2025+type@asset+block@missing.png">'
        )
        links = self.links()
        assert links.rewrite_text(text, to_static=True) is text
        assert links.rewritten == 0

    def test_without_files_links_only_lose_the_host(self):
        links = ImportAssetLinks(SOURCE, DEST)
        text = 'https://lms2.robbo.world/asset-v1:Robbo+SRC+2025+type@asset+block@pic.png'
        assert links.rewrite_text(text, to_static=True) == '/asset-v1:Robbo+SRC+2025+type@asset+block@pic.png'

    def test_values_are_walked_not_changed_in_place(self):
        url = 'https://lms2.robbo.world/asset-v1:Robbo+SRC+2025+type@asset+block@pic.png'
        value = {'certificates': [{'signatories': [{'signature_image_path': url, 'id': 1}]}], 'n': 1}
        updated = self.links().rewrite_value(value)
        assert updated['certificates'][0]['signatories'][0] == {
            'signature_image_path': '/asset-v1:Robbo+DEST+2026+type@asset+block@pic.png', 'id': 1,
        }
        assert value['certificates'][0]['signatories'][0]['signature_image_path'] == url
        unchanged = {'a': ['b', 1, None], 'c': {'d': 'e'}}
        assert self.links().rewrite_value(unchanged) is unchanged
