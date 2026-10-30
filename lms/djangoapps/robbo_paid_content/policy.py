# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (paid content). See NOTICE at repository root.
"""
Which blocks are paid, and who has full access. Docs: docs/paid-content.md in the meta repo.

A block is paid when the course policy (PaidContentPolicy) is on and any of its rules holds:

* the block or its section/subsection is marked «Только полный доступ» (field ``robbo_paid_only``);
* it lies in a section after the first ``free_sections``;
* ``graded_paid`` and the block is a graded problem (the content type gating test).

Full access is an active enrollment in a «verified» mode; course staff are never limited.
The rules are applied in three places, all computed from the live policy, so a change takes effect
at once and nothing is written into the blocks' ``group_access``:

* course block structures (navigation, outline, grades) — transformers.RobboPaidContentTransformer;
* loading a block (rendering a unit, submitting an answer) — access.check_load from courseware access;
* the learning_sequences outline — CMS marks paid sections/subsections with
  ``{OUTLINE_PARTITION_ID: [FULL_GROUP_ID]}`` (``outline_partition_groups``) and
  outline_processor.RobboPaidContentOutlineProcessor hides them when the policy says «hidden».
"""

from edx_django_utils.cache import RequestCache
from opaque_keys.edx.keys import CourseKey

# A key in the learning_sequences ``user_partition_groups`` of paid sections/subsections. 52–99 is the
# range upstream leaves for plugged-in single partitions (xmodule/partitions/partitions.py); only
# RobboPaidContentOutlineProcessor reads it.
OUTLINE_PARTITION_ID = 52
FULL_GROUP_ID = 2

# Marks a paid block in course block structures (``authorization_denial_reason``)
DENIAL_REASON = 'Полный доступ к курсу'

STRUCTURE_BLOCK_TYPES = ('chapter', 'sequential')

_CACHE_NAMESPACE = 'robbo_paid_content.policy'


def normalize_course_key(course_key):
    if isinstance(course_key, str):
        course_key = CourseKey.from_string(course_key)
    return course_key.for_branch(None).replace(version_guid=None)


def get_policy(course_key):
    """The enabled PaidContentPolicy of the course, or None (cached per request; Celery tasks clear it too)."""
    from .models import PaidContentPolicy
    course_key = normalize_course_key(course_key)
    cache = RequestCache(_CACHE_NAMESPACE)
    cached = cache.get_cached_response(str(course_key))
    if cached.is_found:
        return cached.value
    value = PaidContentPolicy.objects.filter(course_key=course_key, is_enabled=True).first()
    cache.set(str(course_key), value)
    return value


def clear_policy_cache():
    """After saving a policy in the same request (Studio «Тип курса»)."""
    RequestCache(_CACHE_NAMESPACE).clear()


def has_full_access(user, course_key):
    """An active enrollment in a «verified» mode (cached per request)."""
    from common.djangoapps.course_modes.models import CourseMode
    from common.djangoapps.student.models import CourseEnrollment
    if user is None or not user.is_authenticated:
        return False
    course_key = normalize_course_key(course_key)
    cache = RequestCache(_CACHE_NAMESPACE)
    cache_key = f'full:{user.id}:{course_key}'
    cached = cache.get_cached_response(cache_key)
    if cached.is_found:
        return cached.value
    mode, is_active = CourseEnrollment.enrollment_mode_for_user(user, course_key)
    value = bool(is_active and mode in CourseMode.VERIFIED_MODES)
    cache.set(cache_key, value)
    return value


def is_graded_problem(block):
    """The same test content type gating uses for «graded content»."""
    return bool(getattr(block, 'graded', False) and block.has_score and getattr(block, 'weight', 0) != 0)


def section_index(section):
    """0-based position of a section in the course, or None."""
    parent = section.get_parent()
    if parent is None:
        return None
    block_ids = [child.block_id for child in parent.children]
    try:
        return block_ids.index(section.location.block_id)
    except ValueError:
        return None


def is_paid_by_data(course_policy, locked, index, graded_problem):
    """The rules on collected data: own or inherited lock, section position, graded problem."""
    if course_policy is None:
        return False
    if locked:
        return True
    if course_policy.free_sections is not None and index is not None and index >= course_policy.free_sections:
        return True
    return bool(course_policy.graded_paid and graded_problem)


def is_paid_block(block, course_policy):
    """The rules on a loaded XBlock, walking up to its section."""
    if course_policy is None:
        return False
    graded_problem = block.scope_ids.block_type not in STRUCTURE_BLOCK_TYPES and is_graded_problem(block)
    locked, index = False, None
    node = block
    while node is not None and node.scope_ids.block_type != 'course':
        block_type = node.scope_ids.block_type
        if block_type in STRUCTURE_BLOCK_TYPES and getattr(node, 'robbo_paid_only', False):
            locked = True
            break
        if block_type == 'chapter':
            index = section_index(node)
            break
        node = node.get_parent()
    return is_paid_by_data(course_policy, locked, index, graded_problem)


def outline_partition_groups(block, course_policy):
    """``{OUTLINE_PARTITION_ID: [FULL_GROUP_ID]}`` for a paid section/subsection of the learning_sequences outline."""
    if block.scope_ids.block_type in STRUCTURE_BLOCK_TYPES and is_paid_block(block, course_policy):
        return {OUTLINE_PARTITION_ID: [FULL_GROUP_ID]}
    return {}
