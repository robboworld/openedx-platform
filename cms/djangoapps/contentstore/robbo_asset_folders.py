# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (course files catalog). See NOTICE at repository root.
"""
Author folders in «Файлы»: a ``robbo_folder`` label on the file, see ``xmodule/contentstore/robbo_asset_attrs.py``.

A folder exists while at least one file carries its label; renaming or deleting a folder is a
bulk move of its files. Empty folders the author has just created live in the browser only.
"""

import re
import unicodedata

from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import AssetKey

from xmodule.contentstore.django import contentstore
from xmodule.contentstore.robbo_asset_attrs import ROBBO_FOLDER_ATTR, effective_folder
from xmodule.exceptions import NotFoundError

FOLDER_PARAM = 'robbo_folder'
MAX_FOLDER_LENGTH = 80
_CONTROL_RE = re.compile(r'[\x00-\x1f\x7f]')
_SPACES_RE = re.compile(r'\s+')


def normalize_folder(name):
    """NFC, no control characters, single spaces, at most 80 characters; ``''`` means no folder."""
    name = unicodedata.normalize('NFC', str(name or ''))
    name = _SPACES_RE.sub(' ', _CONTROL_RE.sub(' ', name)).strip()
    return name[:MAX_FOLDER_LENGTH].strip()


def asset_json_extras(asset):
    """Fields added to every asset in the «Файлы» JSON (``asset`` is a contentstore document)."""
    return {'robbo_folder': effective_folder(asset)}


def apply_upload_folder(request, asset_key, created=True):
    """
    Put a freshly uploaded file into the folder the author had open (``robbo_folder`` form field).

    A replaced file keeps its own folder.
    """
    if not created or FOLDER_PARAM not in request.POST:
        return
    contentstore().set_attrs(asset_key, {ROBBO_FOLDER_ATTR: normalize_folder(request.POST.get(FOLDER_PARAM))})


def move_assets(course_key, asset_ids, folder):
    """
    Set the folder label of the course files ``asset_ids``.

    Returns ``(moved_ids, folder)``; ids of other courses and missing files are skipped.
    """
    folder = normalize_folder(folder)
    store = contentstore()
    moved = []
    for asset_id in asset_ids or []:
        try:
            asset_key = AssetKey.from_string(str(asset_id))
        except InvalidKeyError:
            continue
        if asset_key.course_key.for_branch(None) != course_key.for_branch(None):
            continue
        try:
            store.set_attrs(asset_key, {ROBBO_FOLDER_ATTR: folder})
        except NotFoundError:
            continue
        moved.append(str(asset_key))
    return moved, folder
