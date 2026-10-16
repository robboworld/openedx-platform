"""
Signal handlers for invalidating cached data.

Modifications Copyright (C) 2026 Robbo. See NOTICE at repository root.
"""

import logging

from django.conf import settings
from django.dispatch.dispatcher import receiver
from opaque_keys.edx.locator import LibraryLocator

from xmodule.modulestore.django import SignalHandler, modulestore

from .api import clear_course_from_cache
from .models import BlockStructureModel
from .tasks import update_course_in_cache_v2

log = logging.getLogger(__name__)


@receiver(SignalHandler.course_published)
def update_block_structure_on_course_publish(sender, course_key, **kwargs):  # pylint: disable=unused-argument
    """
    Catches the signal that a course has been published in the module
    store and creates/updates the corresponding cache entry.
    Ignores publish signals from content libraries.
    """
    if isinstance(course_key, LibraryLocator):
        return

    update_course_in_cache_v2.apply_async(
        kwargs=dict(course_id=str(course_key)),
        countdown=settings.BLOCK_STRUCTURES_SETTINGS['COURSE_PUBLISH_TASK_DELAY'],
    )


@receiver(SignalHandler.course_deleted)
def _delete_block_structure_on_course_delete(sender, course_key, **kwargs):  # pylint: disable=unused-argument
    """
    Catches the signal that a course has been deleted from the
    module store and invalidates the corresponding cache entry if one
    exists.
    """
    # Robbo: block_structure rows are matched case-insensitively on MySQL. Deleting a case twin
    # (course-v1:Robbo+X next to course-v1:ROBBO+X) must not clear the other course's structure.
    root_key = modulestore().make_course_usage_key(course_key)
    stored_key = BlockStructureModel.objects.filter(
        data_usage_key=root_key
    ).values_list('data_usage_key', flat=True).first()
    if stored_key is not None and str(stored_key) != str(root_key):
        log.warning('BlockStructure: %s belongs to case twin %s, not cleared.', root_key, stored_key)
        return
    clear_course_from_cache(course_key)
