# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (course groups). See NOTICE at repository root.

"""
«Сбросить ограничения доступа» in the section menu (cms/djangoapps/contentstore/robbo_group_access.py).
"""

from django.urls import reverse

from cms.djangoapps.contentstore.tests.utils import CourseTestCase
from openedx.core.lib.robbo_group_access import deny_key
from xmodule.modulestore import ModuleStoreEnum
from xmodule.modulestore.tests.factories import BlockFactory, CourseFactory
from xmodule.partitions.partitions import Group, UserPartition

PARTITION_ID = 50


class ResetSectionGroupAccessTest(CourseTestCase):
    """A published section with rules at every level, and another restricted section."""

    def setUp(self):
        super().setUp()
        partition = UserPartition(
            PARTITION_ID, 'Content groups', '', [Group(1, 'Group A'), Group(2, 'Group B')], scheme_id='cohort',
        )
        self.course = CourseFactory.create(user_partitions=[partition])
        self.section = self.make_block(self.course, 'chapter', {PARTITION_ID: [1]})
        self.sequence = self.make_block(self.section, 'sequential', {deny_key(PARTITION_ID): [2]})
        self.unit = self.make_block(self.sequence, 'vertical', {}, visible_to_staff_only=True)
        self.component = self.make_block(self.unit, 'html', {PARTITION_ID: [2]})
        self.store.publish(self.section.location, self.user.id)
        self.other_section = self.make_block(self.course, 'chapter', {PARTITION_ID: [2]})

    def make_block(self, parent, category, group_access, **kwargs):
        return BlockFactory.create(
            parent=parent, category=category, group_access=group_access, user_id=self.user.id, **kwargs,
        )

    def reset(self, location, client=None):
        url = reverse('robbo_reset_section_group_access', kwargs={'usage_key_string': str(location)})
        return (client or self.client).post(url)

    def is_explicit(self, location, branch=ModuleStoreEnum.Branch.draft_preferred):
        with self.store.branch_setting(branch, self.course.id):
            block = self.store.get_item(location)
            return block.fields['group_access'].is_set_on(block)

    def test_removes_rules_in_the_section_only(self):
        response = self.reset(self.section.location)
        assert response.status_code == 200
        # the unit's empty rule is removed too, but it restricted nothing
        assert response.json() == {'cleared': 3}
        for block in (self.section, self.sequence, self.unit, self.component):
            assert not self.is_explicit(block.location)
            assert not self.is_explicit(block.location, ModuleStoreEnum.Branch.published_only)
        assert self.store.get_item(self.other_section.location).group_access == {PARTITION_ID: [2]}

    def test_keeps_hide_from_learners(self):
        self.reset(self.section.location)
        assert self.store.get_item(self.unit.location).visible_to_staff_only

    def test_only_a_section(self):
        assert self.reset(self.sequence.location).status_code == 400
        assert self.is_explicit(self.sequence.location)

    def test_needs_studio_write_access(self):
        client, _ = self.create_non_staff_authed_user_client()
        assert self.reset(self.section.location, client).status_code == 403
        assert self.store.get_item(self.section.location).group_access == {PARTITION_ID: [1]}

    def test_post_only(self):
        url = reverse('robbo_reset_section_group_access', kwargs={'usage_key_string': str(self.section.location)})
        assert self.client.get(url).status_code == 405
