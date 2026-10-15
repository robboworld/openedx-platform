# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (course groups). See NOTICE at repository root.

"""
get_group_access_source_info: the restricted section, subsection or unit above a block, which locks the
block's own group access in Studio; get_own_group_access_info: the rule the locked block sets itself.
"""

from cms.djangoapps.contentstore.utils import get_group_access_source_info, get_own_group_access_info
from openedx.core.lib.robbo_group_access import deny_key
from xmodule.modulestore.django import modulestore
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import BlockFactory, CourseFactory
from xmodule.partitions.partitions import Group, UserPartition

PARTITION_ID = 50


class GroupAccessSourceTest(ModuleStoreTestCase):
    """A course with a restricted, an open and a «hide from» section."""

    def setUp(self):
        super().setUp()
        partition = UserPartition(
            PARTITION_ID, 'Content groups', '', [Group(1, 'Group A'), Group(2, 'Group B')], scheme_id='cohort',
        )
        self.course = CourseFactory.create(user_partitions=[partition])
        self.restricted = self.make_section('restricted', {PARTITION_ID: [1]})
        self.hidden = self.make_section('hidden', {deny_key(PARTITION_ID): [2]})
        self.open = self.make_section('open', {})

    def make_section(self, name, group_access):
        section = BlockFactory.create(
            parent=self.course, category='chapter', display_name=f'Section {name}', group_access=group_access,
        )
        sequence = BlockFactory.create(parent=section, category='sequential', display_name=f'Subsection {name}')
        unit = BlockFactory.create(parent=sequence, category='vertical', display_name=f'Unit {name}')
        component = BlockFactory.create(parent=unit, category='html', display_name=f'Component {name}')
        return [modulestore().get_item(block.location) for block in (section, sequence, unit, component)]

    def test_restricted_section_locks_everything_inside(self):
        section, sequence, unit, component = self.restricted
        assert get_group_access_source_info(section) is None
        expected = {
            'category': 'chapter',
            'display_name': 'Section restricted',
            'selected_groups_label': 'Group A',
            'access_mode': 'allow',
        }
        for block in (sequence, unit, component):
            assert get_group_access_source_info(block) == expected

    def test_hide_from_rule_locks_too(self):
        _, sequence, _, _ = self.hidden
        source = get_group_access_source_info(sequence)
        assert source['selected_groups_label'] == 'Group B'
        assert source['access_mode'] == 'deny'

    def test_open_section_locks_nothing(self):
        for block in self.open:
            assert get_group_access_source_info(block) is None

    def test_nearest_restriction_wins(self):
        _, sequence, unit, component = self.open
        sequence.group_access = {PARTITION_ID: [2]}
        modulestore().update_item(sequence, self.user.id)
        unit = modulestore().get_item(unit.location)
        component = modulestore().get_item(component.location)
        assert get_group_access_source_info(unit)['display_name'] == 'Subsection open'
        assert get_group_access_source_info(component)['category'] == 'sequential'

    def test_own_rule_of_a_locked_block(self):
        _, sequence, unit, _ = self.restricted
        unit.group_access = {deny_key(PARTITION_ID): [2]}
        modulestore().update_item(unit, self.user.id)
        unit = modulestore().get_item(unit.location)
        assert get_own_group_access_info(unit) == {'selected_groups_label': 'Group B', 'access_mode': 'deny'}
        # the inherited rule of the section is not the subsection's own
        assert get_own_group_access_info(sequence) is None

    def test_empty_own_rule_is_not_shown(self):
        _, sequence, _, _ = self.restricted
        sequence.group_access = {}
        modulestore().update_item(sequence, self.user.id)
        assert get_own_group_access_info(modulestore().get_item(sequence.location)) is None
