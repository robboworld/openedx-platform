# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (certificate signatures). See NOTICE at repository root.
"""
Certificate signature images that point at another course.

A signatory stores its image as a full asset path, ``/asset-v1:<course>+type@asset+block@<name>``.
Export/import and a course rerun copy the file into the new course but keep the path verbatim,
so the copy keeps loading the image from the original course: on another instance, or once the
original course or file is gone, the signature is not drawn. ``relink_course_signatures`` points
such paths at the new course's own copy of the file (same name); a path is left alone when the
course has no such file. Called after the import (``xml_importer.py``, files are imported after
the course block) and after a rerun (``cms/djangoapps/contentstore/tasks.py``).
"""

import copy
import logging

from opaque_keys import InvalidKeyError

from xmodule.contentstore.content import StaticContent
from xmodule.modulestore import ModuleStoreEnum

log = logging.getLogger(__name__)


def signature_asset_key(path):
    """Asset key of a signature image path, or None when the path is empty or not an asset path."""
    path = (path or '').strip()
    if not path:
        return None
    try:
        return StaticContent.get_location_from_path(path)
    except InvalidKeyError:
        return None


def relink_certificate_signatures(certificates, course_key, content_store):
    """
    Copy of ``certificates`` with foreign signature paths pointed at the course's own files.

    Returns None when no path changed.
    """
    data = copy.deepcopy(certificates or {})
    changed = False
    for certificate in data.get('certificates') or []:
        for signatory in certificate.get('signatories') or []:
            asset_key = signature_asset_key(signatory.get('signature_image_path'))
            if asset_key is None or asset_key.course_key == course_key:
                continue
            own_key = course_key.make_asset_key(asset_key.block_type, asset_key.block_id)
            if content_store.find(own_key, throw_on_not_found=False) is None:
                continue
            signatory['signature_image_path'] = StaticContent.serialize_asset_key_with_slash(own_key)
            changed = True
    return data if changed else None


def relink_course_signatures(store, content_store, course_key, user_id):
    """
    Save the course with relinked signature paths; True when something changed.

    Never raises: a failure here must not fail the import or the rerun around it.
    """
    try:
        with store.branch_setting(ModuleStoreEnum.Branch.draft_preferred, course_key):
            course = store.get_course(course_key)
            if course is None:
                return False
            updated = relink_certificate_signatures(course.certificates, course_key, content_store)
            if updated is None:
                return False
            course.certificates = updated
            store.update_item(course, user_id)
    except Exception:  # pylint: disable=broad-except
        log.exception('robbo signatures: could not relink signature images of %s', course_key)
        return False
    log.info('robbo signatures: signature images of %s now point at its own files', course_key)
    return True
