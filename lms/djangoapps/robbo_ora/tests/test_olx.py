# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
"""Robbo settings of an ORA block in OLX (cms/djangoapps/contentstore/robbo_ora_limits.py)."""

from django.test import TestCase
from lxml import etree
from openassessment.xblock.openassessmentblock import OpenAssessmentBlock
from xblock.field_data import DictFieldData
from xblock.fields import ScopeIds
from xblock.test.tools import TestRuntime

from cms.djangoapps.contentstore.robbo_ora_limits import ROBBO_ORA_DEFAULT_MAX_FILES_COUNT as DEFAULT_MAX_FILES

KEYS = ScopeIds('user', 'openassessment', 'definition', 'usage')


def make_block():
    runtime = TestRuntime(services={'field-data': DictFieldData({})})
    return runtime.construct_xblock_from_class(OpenAssessmentBlock, KEYS)


def export(block):
    node = etree.Element('root')
    block.add_xml_to_node(node)
    return node


def import_block(node):
    return OpenAssessmentBlock.parse_xml(node, make_block().runtime, KEYS)


class OraOlxTests(TestCase):
    """Export and import of the settings."""

    def test_settings_survive_export_and_import(self):
        block = make_block()
        block.max_files_count = 5
        block.robbo_large_files = True
        block.robbo_file_size_limits = {'pdf': 20, 'sb3': 50}
        block.robbo_auto_score = True
        block.robbo_allow_retake = True

        # A real archive holds the node as text, so go through it.
        imported = import_block(etree.fromstring(etree.tostring(export(block))))

        assert imported.max_files_count == 5
        assert imported.robbo_large_files is True
        assert imported.robbo_file_size_limits == {'pdf': 20, 'sb3': 50}
        assert imported.robbo_auto_score is True
        assert imported.robbo_allow_retake is True

    def test_setting_turned_off_stays_off(self):
        block = make_block()
        block.robbo_allow_retake = False
        assert import_block(export(block)).robbo_allow_retake is False

    def test_settings_never_touched_stay_out_of_olx(self):
        attributes = export(make_block()).attrib
        assert not [name for name in attributes if name.startswith('robbo_') or name == 'max_files_count']

    def test_archive_without_the_settings_gets_defaults(self):
        imported = import_block(export(make_block()))
        assert imported.max_files_count == DEFAULT_MAX_FILES
        assert imported.robbo_file_size_limits == {}
        assert imported.robbo_auto_score is False
        assert imported.robbo_allow_retake is False

    def test_bad_value_does_not_stop_the_import(self):
        node = export(make_block())
        node.set('max_files_count', 'много')
        node.set('robbo_file_size_limits', '{not valid')
        node.set('robbo_allow_retake', 'true')
        imported = import_block(node)
        assert imported.max_files_count == DEFAULT_MAX_FILES
        assert imported.robbo_file_size_limits == {}
        assert imported.robbo_allow_retake is True

    def test_learner_state_is_not_exported(self):
        block = make_block()
        block.robbo_retake_granted = True
        assert 'robbo_retake_granted' not in export(block).attrib
