# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (course groups). See NOTICE at repository root.

"""
«Сбросить ограничения доступа» in the section menu of the course outline: removes the group access rules
(both «show only to» and «hide from», openedx/core/lib/robbo_group_access.py) from the section and from
everything inside it. «Hide from learners» (staff lock) is not touched.

Each block goes through the regular Studio save with publish="republish", like a change in «Настроить»:
what was published stays published, drafts stay drafts.
"""

import logging

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404
from django.views.decorators.http import require_POST
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import UsageKey

from common.djangoapps.student.auth import has_studio_write_access
from common.djangoapps.util.json_request import JsonResponse
from xmodule.modulestore.django import modulestore

from .xblock_storage_handlers.view_handlers import _save_xblock

log = logging.getLogger(__name__)


def _with_descendants(block):
    yield block
    if block.has_children:
        for child in block.get_children():
            yield from _with_descendants(child)


# Not atomic, like the xblock handler: publishing starts async tasks that must see the changes.
@transaction.non_atomic_requests
@require_POST
@login_required
def reset_section_group_access(request, usage_key_string):
    try:
        usage_key = UsageKey.from_string(usage_key_string)
    except InvalidKeyError as exc:
        raise Http404 from exc
    if usage_key.block_type != 'chapter':
        return JsonResponse({'error': 'Only a section can be reset.'}, 400)
    if not has_studio_write_access(request.user, usage_key.course_key):
        raise PermissionDenied()

    store = modulestore()
    cleared = 0
    with store.bulk_operations(usage_key.course_key):
        section = store.get_item(usage_key)
        for block in list(_with_descendants(section)):
            if not block.fields['group_access'].is_set_on(block):
                continue
            had_rule = any((block.group_access or {}).values())
            # None removes the field: the block inherits again instead of keeping an empty rule
            _save_xblock(request.user, block, metadata={'group_access': None}, publish='republish')
            cleared += int(had_rule)
    log.info('robbo: %s reset group access in %s, %s rules removed', request.user.username, usage_key, cleared)
    return JsonResponse({'cleared': cleared})
