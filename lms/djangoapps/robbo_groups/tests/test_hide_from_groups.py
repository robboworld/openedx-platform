# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (course groups). See NOTICE at repository root.

"""
«Hide from groups» access rules (openedx/core/lib/robbo_group_access.py): a block hidden from a content
group is unavailable to that group and stays available to everyone else, learners without a group too.
"""

from datetime import datetime, timezone

from common.djangoapps.student.models import CourseEnrollment
from common.djangoapps.student.tests.factories import UserFactory
from lms.djangoapps.course_blocks.api import get_course_blocks
from lms.djangoapps.courseware.access import has_access
from openedx.core.djangoapps.content.learning_sequences.api.processors.cohort_partition_groups import (
    CohortPartitionGroupsOutlineProcessor,
)
from openedx.core.djangoapps.course_groups.cohorts import add_cohort, add_user_to_cohort
from openedx.core.djangoapps.course_groups.models import CourseCohort
from openedx.core.djangoapps.course_groups.tests.helpers import config_course_cohorts
from openedx.core.djangoapps.course_groups.views import link_cohort_to_partition_group
from openedx.core.djangolib.testing.utils import skip_unless_lms
from openedx.core.lib.robbo_group_access import deny_key, split_group_access
from xmodule.modulestore.django import modulestore
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import BlockFactory, CourseFactory
from xmodule.partitions.partitions import Group, UserPartition

PARTITION_ID = 50
GROUP_A = 1
GROUP_B = 2


def test_split_group_access():
    assert split_group_access({50: [1], -50: [2], 51: [], -52: None}) == ({50: [1]}, {50: [2]})


@skip_unless_lms
class HideFromGroupsTests(ModuleStoreTestCase):
    """Learners of content groups A and B and a learner without a group."""

    def setUp(self):
        super().setUp()
        partition = UserPartition(
            PARTITION_ID, 'Content groups', '', [Group(GROUP_A, 'A'), Group(GROUP_B, 'B')], scheme_id='cohort',
        )
        self.course = CourseFactory.create(user_partitions=[partition])
        # Content first: split auto-publishing of new children breaks after the course itself is re-saved.
        self.hidden_from_b = self.make_section({deny_key(PARTITION_ID): [GROUP_B]})
        self.only_b = self.make_section({PARTITION_ID: [GROUP_B]})
        self.component_hidden_from_a = self.make_section(
            component_group_access={deny_key(PARTITION_ID): [GROUP_A]},
        )
        self.a_and_b_component_hidden_from_a = self.make_section(
            {PARTITION_ID: [GROUP_A, GROUP_B]},
            component_group_access={deny_key(PARTITION_ID): [GROUP_A]},
        )
        config_course_cohorts(self.course, is_cohorted=True)
        self.users = {}
        for name, group_id in (('a', GROUP_A), ('b', GROUP_B), ('none', None)):
            user = UserFactory()
            CourseEnrollment.enroll(user, self.course.id)
            cohort = add_cohort(self.course.id, f'cohort {name}', CourseCohort.MANUAL)
            if group_id is not None:
                link_cohort_to_partition_group(cohort, PARTITION_ID, group_id)
            add_user_to_cohort(cohort, user)
            self.users[name] = user

    def make_section(self, group_access=None, component_group_access=None):
        section = BlockFactory.create(parent=self.course, category='chapter', group_access=group_access or {})
        sequence = BlockFactory.create(parent=section, category='sequential')
        unit = BlockFactory.create(parent=sequence, category='vertical')
        component = BlockFactory.create(parent=unit, category='html', group_access=component_group_access or {})
        return section, component

    def visible(self, user, location):
        in_structure = location in get_course_blocks(user, self.course.location)
        can_load = bool(has_access(user, 'load', modulestore().get_item(location), self.course.id))
        assert in_structure == can_load, 'course structure and block access disagree'
        return in_structure

    def visible_to(self, location):
        return {name for name, user in self.users.items() if self.visible(user, location)}

    def test_section_hidden_from_a_group(self):
        section, component = self.hidden_from_b
        assert self.visible_to(section.location) == {'a', 'none'}
        assert self.visible_to(component.location) == {'a', 'none'}

    def test_allow_list_unchanged(self):
        section, component = self.only_b
        assert self.visible_to(section.location) == {'b'}
        assert self.visible_to(component.location) == {'b'}

    def test_hidden_component_inside_an_open_section(self):
        section, component = self.component_hidden_from_a
        assert self.visible_to(section.location) == {'a', 'b', 'none'}
        assert self.visible_to(component.location) == {'b', 'none'}

    def test_rules_add_up_down_the_tree(self):
        section, component = self.a_and_b_component_hidden_from_a
        assert self.visible_to(section.location) == {'a', 'b'}
        assert self.visible_to(component.location) == {'b'}

    def test_outline_processor(self):
        processor = CohortPartitionGroupsOutlineProcessor(self.course.id, self.users['b'], datetime.now(timezone.utc))
        processor.load_data(None)
        hidden_from_b = {deny_key(PARTITION_ID): frozenset([GROUP_B])}
        hidden_from_a = {deny_key(PARTITION_ID): frozenset([GROUP_A])}
        assert processor._is_user_excluded_by_partition_group(hidden_from_b)  # pylint: disable=protected-access
        assert not processor._is_user_excluded_by_partition_group(hidden_from_a)  # pylint: disable=protected-access

        processor = CohortPartitionGroupsOutlineProcessor(
            self.course.id, self.users['none'], datetime.now(timezone.utc),
        )
        processor.load_data(None)
        assert not processor._is_user_excluded_by_partition_group(hidden_from_b)  # pylint: disable=protected-access
        assert processor._is_user_excluded_by_partition_group(  # pylint: disable=protected-access
            {PARTITION_ID: frozenset([GROUP_B])}
        )
