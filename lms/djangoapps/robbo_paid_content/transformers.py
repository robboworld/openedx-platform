# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (paid content). See NOTICE at repository root.
"""
Course blocks transformer for paid content (navigation, course outline, grades).

``collect`` (on publish, in Studio or the LMS) stores, per block, what the rules need and what does
not depend on the policy: the «Только полный доступ» lock (own or inherited from a section/subsection),
the position of its section, whether it is a graded problem. ``transform`` applies the live policy
(policy.is_paid_by_data) to a learner on the free path:

* navigation (default access transformers): removed when the display is «hidden», otherwise kept
  locked — ``authorization_denial_reason``/``_message`` set as the UserPartitionTransformer does;
* grades (``for_grades=True``, lms/djangoapps/grades/course_data.py): removed when the grading is
  «excluded», otherwise kept, so a paid problem counts as not done.

Registered in setup.py under ``openedx.block_structure_transformer`` as ``robbo_paid_content``.
"""

from lms.djangoapps.courseware.access import has_access
from lms.djangoapps.robbo_changelog.labels import pick
from openedx.core.djangoapps.content.block_structure.transformer import BlockStructureTransformer

from . import policy
from .access import TEXTS
from .models import PaidContentPolicy


class RobboPaidContentTransformer(BlockStructureTransformer):
    """Locks or removes the blocks the course policy makes paid, for learners on the free path."""

    WRITE_VERSION = 1
    READ_VERSION = 1
    PAID_DATA = 'paid_data'

    def __init__(self, for_grades=False):
        self.for_grades = for_grades

    @classmethod
    def name(cls):
        return 'robbo_paid_content'

    @classmethod
    def collect(cls, block_structure):
        root_key = block_structure.root_block_usage_key
        section_positions = {key: index for index, key in enumerate(block_structure.get_children(root_key))}
        for block_key in block_structure.topological_traversal():
            if block_key == root_key:
                continue
            xblock = block_structure.get_xblock(block_key)
            block_type = block_key.block_type
            parent_data = [
                block_structure.get_transformer_block_field(parent_key, cls, cls.PAID_DATA)
                for parent_key in block_structure.get_parents(block_key)
            ]
            parent_data = [data for data in parent_data if data is not None]
            own_lock = block_type in policy.STRUCTURE_BLOCK_TYPES and bool(getattr(xblock, 'robbo_paid_only', False))
            # A block reused under several parents is locked only if every parent is
            locked = own_lock or bool(parent_data) and all(data['locked'] for data in parent_data)
            if block_type == 'chapter':
                index = section_positions.get(block_key)
            else:
                indexes = [data['index'] for data in parent_data if data['index'] is not None]
                index = min(indexes) if indexes else None
            graded_problem = block_type not in policy.STRUCTURE_BLOCK_TYPES and policy.is_graded_problem(xblock)
            block_structure.set_transformer_block_field(block_key, cls, cls.PAID_DATA, {
                'locked': locked, 'index': index, 'graded_problem': graded_problem,
            })

    def transform(self, usage_info, block_structure):
        course_policy = policy.get_policy(usage_info.course_key)
        if course_policy is None:
            return
        user = usage_info.user
        if has_access(user, 'staff', usage_info.course_key) or policy.has_full_access(user, usage_info.course_key):
            return
        if self.for_grades:
            remove = course_policy.grading == PaidContentPolicy.GRADING_EXCLUDED
        else:
            remove = course_policy.display == PaidContentPolicy.DISPLAY_HIDDEN

        paid = set()
        for block_key in block_structure.topological_traversal():
            data = block_structure.get_transformer_block_field(block_key, self, self.PAID_DATA)
            if data and policy.is_paid_by_data(course_policy, data['locked'], data['index'], data['graded_problem']):
                paid.add(block_key)
        if not paid:
            return
        if remove:
            block_structure.remove_block_traversal(lambda block_key: block_key in paid)
            return
        message = pick(TEXTS['message'])
        for block_key in paid:
            block_structure.override_xblock_field(block_key, 'authorization_denial_reason', policy.DENIAL_REASON)
            block_structure.override_xblock_field(block_key, 'authorization_denial_message', message)
