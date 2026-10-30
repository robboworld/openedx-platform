# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (paid content). See NOTICE at repository root.
"""Tests for paid content: rules, course blocks (navigation and grades), loading a block, outline."""

from types import SimpleNamespace

import ddt
from django.test import override_settings

from common.djangoapps.course_modes.models import CourseMode
from common.djangoapps.course_modes.tests.factories import CourseModeFactory
from common.djangoapps.student.models import CourseEnrollment
from common.djangoapps.student.tests.factories import UserFactory
from lms.djangoapps.commerce.models import CommerceConfiguration
from lms.djangoapps.course_blocks.api import get_course_blocks
from lms.djangoapps.courseware.access import has_access
from lms.djangoapps.robbo_paid_content import policy
from lms.djangoapps.robbo_paid_content.models import PaidContentPolicy
from lms.djangoapps.robbo_paid_content.outline_processor import RobboPaidContentOutlineProcessor
from openedx.core.djangolib.testing.utils import skip_unless_lms
from xmodule.modulestore.django import modulestore
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import BlockFactory, CourseFactory


@skip_unless_lms
@ddt.ddt
class PaidContentTests(ModuleStoreTestCase):
    """
    Course: section 1 (free, a graded problem), section 2 (subsection locked «Только полный доступ»,
    an ungraded problem next to it in a free subsection), section 3 (nothing marked).
    """

    def setUp(self):
        super().setUp()
        self.course = CourseFactory.create()
        self.key = self.course.id
        def add(parent, block_type, block_id, **metadata):
            return BlockFactory.create(
                parent=parent, category=block_type, location=self.key.make_usage_key(block_type, block_id),
                metadata=metadata,
            )

        self.s1 = add(self.course, 'chapter', 's1')
        self.s1_seq = add(self.s1, 'sequential', 's1_seq', graded=True, format='Homework')
        self.s1_unit = add(self.s1_seq, 'vertical', 's1_unit')
        self.graded = add(self.s1_unit, 'problem', 'graded')
        self.s2 = add(self.course, 'chapter', 's2')
        self.s2_locked = add(self.s2, 'sequential', 's2_locked', robbo_paid_only=True)
        self.locked_unit = add(self.s2_locked, 'vertical', 'locked_unit')
        self.locked_html = add(self.locked_unit, 'html', 'locked_html')
        self.s2_free = add(self.s2, 'sequential', 's2_free')
        self.s2_free_unit = add(self.s2_free, 'vertical', 's2_free_unit')
        self.s3 = add(self.course, 'chapter', 's3')
        self.s3_seq = add(self.s3, 'sequential', 's3_seq')
        self.s3_unit = add(self.s3_seq, 'vertical', 's3_unit')
        self.free = UserFactory.create()
        self.full = UserFactory.create()
        CourseModeFactory.create(course_id=self.key, mode_slug=CourseMode.HONOR)
        CourseModeFactory.create(course_id=self.key, mode_slug=CourseMode.VERIFIED, min_price=1990, sku='SKU-FULL')
        CourseEnrollment.enroll(self.free, self.key, CourseMode.HONOR)
        CourseEnrollment.enroll(self.full, self.key, CourseMode.VERIFIED)
        self.policy = PaidContentPolicy.objects.create(course_key=self.key, is_enabled=True)

    def _set(self, **fields):
        for name, value in fields.items():
            setattr(self.policy, name, value)
        self.policy.save()
        policy.clear_policy_cache()

    def _keys(self, user, for_grades=False):
        structure = get_course_blocks(user, self.course.location, robbo_for_grades=for_grades)
        return set(structure), structure

    def _block(self, block):
        return modulestore().get_item(block.location)

    def test_rules_on_loaded_blocks(self):
        paid = lambda block: policy.is_paid_block(self._block(block), policy.get_policy(self.key))  # noqa: E731
        assert paid(self.s2_locked) and paid(self.locked_html)
        assert not paid(self.s2_free_unit) and not paid(self.graded) and not paid(self.s3_unit)
        self._set(free_sections=2)
        assert paid(self.s3) and paid(self.s3_unit) and not paid(self.s2_free_unit)
        self._set(graded_paid=True)
        assert paid(self.graded) and not paid(self.s1_unit)
        self._set(is_enabled=False)
        assert not paid(self.locked_html)

    def test_locked_navigation_keeps_blocks_with_a_message(self):
        keys, structure = self._keys(self.free)
        assert self.locked_html.location in keys
        assert structure.get_xblock_field(self.locked_html.location, 'authorization_denial_reason') == \
            policy.DENIAL_REASON
        assert structure.get_xblock_field(self.s2_free_unit.location, 'authorization_denial_reason') is None

    def test_hidden_navigation_removes_paid_blocks(self):
        self._set(display=PaidContentPolicy.DISPLAY_HIDDEN, free_sections=2)
        keys, _structure = self._keys(self.free)
        assert self.s2_locked.location not in keys and self.locked_html.location not in keys
        assert self.s3.location not in keys
        assert self.s2_free_unit.location in keys
        # Full access and course staff see everything
        assert self.locked_html.location in self._keys(self.full)[0]
        assert self.s3_unit.location in self._keys(self.user)[0]

    @ddt.data(
        (PaidContentPolicy.GRADING_ZERO, True),
        (PaidContentPolicy.GRADING_EXCLUDED, False),
    )
    @ddt.unpack
    def test_grades_follow_the_grading_setting(self, grading, problem_counted):
        # Display and grading are independent: hidden in navigation, still counted in the grade, and back
        self._set(graded_paid=True, grading=grading, display=PaidContentPolicy.DISPLAY_HIDDEN)
        assert (self.graded.location in self._keys(self.free, for_grades=True)[0]) is problem_counted
        assert self.graded.location not in self._keys(self.free)[0]
        assert self.graded.location in self._keys(self.full, for_grades=True)[0]

    @override_settings(ROBBO_PAYMENTS_ENABLED=True)
    def test_loading_a_paid_block(self):
        CommerceConfiguration.objects.update_or_create(
            id=1, defaults={'enabled': True, 'checkout_on_ecommerce_service': True, 'basket_checkout_page': '/basket/add/'},
        )
        html = self._block(self.locked_html)
        denied = has_access(self.free, 'load', html, self.key)
        assert not denied
        assert denied.error_code == 'robbo_paid_content'
        assert 'sku=SKU-FULL' in denied.user_fragment.content
        assert has_access(self.full, 'load', html, self.key)
        assert has_access(self.free, 'load', self._block(self.s2_free_unit), self.key)
        # Hidden: no message, the block is just left out
        self._set(display=PaidContentPolicy.DISPLAY_HIDDEN)
        denied = has_access(self.free, 'load', html, self.key)
        assert not denied and denied.user_fragment is None and denied.user_message is None

    def test_outline_marks_and_processor(self):
        self._set(free_sections=2)
        assert policy.outline_partition_groups(self._block(self.s2_locked), self.policy) == {
            policy.OUTLINE_PARTITION_ID: [policy.FULL_GROUP_ID],
        }
        assert policy.outline_partition_groups(self._block(self.s3), self.policy)
        assert policy.outline_partition_groups(self._block(self.s1), self.policy) == {}
        paid = {policy.OUTLINE_PARTITION_ID: [policy.FULL_GROUP_ID]}
        outline = SimpleNamespace(sections=[
            SimpleNamespace(usage_key='s2', user_partition_groups={}, sequences=[
                SimpleNamespace(usage_key='s2_locked', user_partition_groups=paid),
                SimpleNamespace(usage_key='s2_free', user_partition_groups={}),
            ]),
            SimpleNamespace(usage_key='s3', user_partition_groups=paid, sequences=[
                SimpleNamespace(usage_key='s3_seq', user_partition_groups={}),
            ]),
        ])
        processor = RobboPaidContentOutlineProcessor(self.key, self.free, None)
        processor.load_data(outline)
        assert processor.usage_keys_to_remove(outline) == set()  # locked: stays in the outline
        self._set(display=PaidContentPolicy.DISPLAY_HIDDEN)
        processor.load_data(outline)
        assert processor.usage_keys_to_remove(outline) == {'s2_locked', 's3', 's3_seq'}
        full_processor = RobboPaidContentOutlineProcessor(self.key, self.full, None)
        full_processor.load_data(outline)
        assert full_processor.usage_keys_to_remove(outline) == set()
