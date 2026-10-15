# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (course groups). See NOTICE at repository root.

"""
«Hide from groups» access rules.

Upstream ``group_access`` is an allow list: ``{partition_id: [group ids]}`` shows a block only to
learners in those groups. Robbo adds the opposite rule under the negated partition id:
``{-partition_id: [group ids]}`` hides the block from learners in those groups and keeps it for
everyone else, learners without a group included. Studio sets one rule or the other per block.

Both rules live in the same field, so inheritance, OLX export/import, copy-paste, Studio saving and
the learning_sequences outline (signed partition ids) carry the new one as is. Only the code that
interprets the field knows the sign:

- lms/djangoapps/lms_xblock/mixin.py: merging rules down the tree, Studio validation;
- lms/djangoapps/courseware/access.py: loading a block;
- lms/djangoapps/course_blocks/transformers/user_partitions.py: course structure (outline, grades);
- openedx/core/djangoapps/content/learning_sequences/api/processors/*_partition_groups.py: outline;
- cms/djangoapps/contentstore/utils.py, views/preview.py, course_group_config.py: Studio.
"""


def deny_key(partition_id):
    """
    The group_access key of the «hide from groups» rule for this partition, or None for partition id 0
    (some old courses and tests have one), whose negation would be the allow key itself.
    """
    return -partition_id if partition_id > 0 else None


def is_deny_key(key):
    return key is not None and key < 0


def split_group_access(group_access):
    """
    Split group_access into ``(allow, deny)``, both keyed by the (positive) partition id.
    Empty group lists mean «no rule» and are dropped, as upstream does for allow lists.
    """
    allow, deny = {}, {}
    for key, group_ids in (group_access or {}).items():
        if not group_ids:
            continue
        if is_deny_key(key):
            deny[-key] = group_ids
        else:
            allow[key] = group_ids
    return allow, deny
