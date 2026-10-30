# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (paid content). See NOTICE at repository root.
"""
learning_sequences outline processor: when the course policy hides paid content, sections and
subsections that are paid (CMS writes ``{OUTLINE_PARTITION_ID: [FULL_GROUP_ID]}`` into their outline
``user_partition_groups``, cms/djangoapps/contentstore/outlines.py) disappear from the outline of a
learner on the free path. With «locked» they stay: the units inside show the paywall.
"""

from openedx.core.djangoapps.content.learning_sequences.api.processors.base import OutlineProcessor

from . import policy
from .models import PaidContentPolicy


class RobboPaidContentOutlineProcessor(OutlineProcessor):
    """Removes paid sections/subsections for learners on the free path when the policy says «hidden»."""

    def __init__(self, course_key, user, at_time):
        super().__init__(course_key, user, at_time)
        self.hide = False

    def load_data(self, full_course_outline):
        course_policy = policy.get_policy(self.course_key)
        if course_policy is None or course_policy.display != PaidContentPolicy.DISPLAY_HIDDEN:
            return
        # Staff never reach usage_keys_to_remove (learning_sequences can_see_all_content)
        self.hide = not policy.has_full_access(self.user, self.course_key)

    @staticmethod
    def _is_paid(user_partition_groups):
        return bool((user_partition_groups or {}).get(policy.OUTLINE_PARTITION_ID))

    def usage_keys_to_remove(self, full_course_outline):
        if not self.hide:
            return set()
        removed = set()
        for section in full_course_outline.sections:
            section_paid = self._is_paid(section.user_partition_groups)
            if section_paid:
                removed.add(section.usage_key)
            for sequence in section.sequences:
                if section_paid or self._is_paid(sequence.user_partition_groups):
                    removed.add(sequence.usage_key)
        return removed
