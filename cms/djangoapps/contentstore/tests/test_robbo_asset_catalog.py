# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (course files catalog). See NOTICE at repository root.
"""
Tests for the «Файлы» catalog helpers that need no database: reference parsing, field texts,
folder names and upload suffixes.
"""

import json
from unittest import TestCase

from cms.djangoapps.contentstore.robbo_asset_folders import normalize_folder
from cms.djangoapps.contentstore.robbo_asset_uploads import normalize_name, suffixed_names
from cms.djangoapps.contentstore.robbo_asset_usage import _value_text, asset_names, extract_refs
from xmodule.contentstore.robbo_asset_attrs import copied_attrs, effective_folder, project_fields


class ExtractRefsTest(TestCase):
    """Every URL form of a course file resolves to its asset key name."""

    def names(self, text):
        return {name for name, _course in extract_refs(text)}

    def test_static_path(self):
        assert 'robot.png' in self.names('<img src="/static/robot.png" alt="">')

    def test_static_subdirectory_is_flattened(self):
        assert 'images_unit1_robot.png' in self.names('<img src="/static/images/unit1/robot.png">')

    def test_query_fragment_and_entities_are_cut(self):
        assert 'robot.png' in self.names('<a href="/static/robot.png?raw&amp;x=1#top">')
        assert 'robot.png' in self.names('src=&quot;/static/robot.png&quot;')

    def test_percent_encoded_cyrillic(self):
        assert 'фото.png' in self.names('<img src="/static/%D1%84%D0%BE%D1%82%D0%BE.png">')

    def test_space_becomes_underscore_like_the_key(self):
        assert 'my_file.pdf' in self.names('<a href="/static/my%20file.pdf">')

    def test_asset_key_from_another_run_and_host(self):
        refs = extract_refs(
            '<img src="https://lms.example.com/asset-v1:ROBBO+SC1+2023_C1_en+type@asset+block@podpis.png">'
        )
        assert ('podpis.png', 'ROBBO+SC1+2023_C1_en') in refs

    def test_versioned_lms_url(self):
        refs = extract_refs('/assets/courseware/v1/0123abcd/asset-v1:ORG+C+R+type@asset+block/robot.png')
        assert ('robot.png', 'ORG+C+R') in refs

    def test_c4x(self):
        assert ('robot.png', 'ORG+C') in extract_refs('<img src="/c4x/ORG/C/asset/robot.png">')

    def test_text_without_references(self):
        assert extract_refs('<p>Обычный текст про asset management</p>') == set()

    def test_decomposed_name_matches_nfc_and_legacy_keys(self):
        names = asset_names('и\u0306.png')
        assert 'й.png' in names  # uploads are normalized to NFC
        assert 'и_.png' in names  # older macOS uploads: the combining mark became "_"


class ValueTextTest(TestCase):
    """Field values become searchable text; JSON with \\u escapes (ORA prompts) is unescaped."""

    def test_json_string_is_unescaped(self):
        prompt = json.dumps([{'description': '<img src="/static/фото.png">'}])
        assert '\\u' in prompt
        assert '/static/фото.png' in _value_text(prompt)

    def test_dict_value(self):
        assert '/static/фон.png' in _value_text({'background': '/static/фон.png'})

    def test_scalars_are_skipped(self):
        assert _value_text(5) == ''
        assert _value_text(None) == ''
        assert _value_text(True) == ''


class FolderAndNameTest(TestCase):
    """Folder labels and upload names follow the same rules everywhere."""

    def test_normalize_folder(self):
        assert normalize_folder('  Урок \t 3\n') == 'Урок 3'
        assert normalize_folder(None) == ''
        assert len(normalize_folder('я' * 200)) == 80

    def test_normalize_name_nfc(self):
        assert normalize_name('и\u0306.png') == 'й.png'

    def test_suffixed_names(self):
        names = suffixed_names('Слайд13.JPG')
        assert next(names) == 'Слайд13-2.JPG'
        assert next(names) == 'Слайд13-3.JPG'

    def test_effective_folder(self):
        assert effective_folder({'robbo_folder': 'Урок 1', 'import_path': 'img/a.png'}) == 'Урок 1'
        assert effective_folder({'robbo_folder': '', 'import_path': 'img/a.png'}) == ''
        assert effective_folder({'import_path': 'images/unit1/a.png'}) == 'images/unit1'
        assert effective_folder({'import_path': 'a.png'}) == ''
        assert effective_folder({'import_path': 'components/html/x/a.png'}) == ''
        assert effective_folder({}) == ''

    def test_copied_and_projected_attrs(self):
        assert copied_attrs({'robbo_folder': 'A', 'displayname': 'x'}) == {'robbo_folder': 'A'}
        assert copied_attrs({'displayname': 'x'}) == {}
        assert project_fields() == {'robbo_folder': 1}
