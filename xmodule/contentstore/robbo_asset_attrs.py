# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (course files catalog). See NOTICE at repository root.
"""
Robbo attributes of course files (GridFS file documents) that must travel with the file.

``robbo_folder`` — the author's folder in «Файлы». It is a label only: the asset key and the
``/static/<name>`` URL never depend on it, so moving a file between folders breaks no link.

The contentstore rewrites a file document on every upload and copies only fixed fields on a
course rerun; the hooks in ``mongo.py`` and ``xml_importer.py`` call the helpers below so the
label survives a re-upload, a rerun and an export/import round trip (export already writes every
attribute to ``policies/assets.json``). Other Open edX instances ignore the extra key.
"""

import os

ROBBO_FOLDER_ATTR = 'robbo_folder'
ROBBO_KEPT_ATTRS = (ROBBO_FOLDER_ATTR,)
# import_path directories that are not author folders (library component assets).
SEED_SKIPPED_PREFIXES = ('components/',)


def kept_attrs(fs_files, content_id):
    """Robbo attributes of the existing file document ``content_id`` (empty when there is none)."""
    doc = fs_files.find_one({'_id': content_id}, {attr: 1 for attr in ROBBO_KEPT_ATTRS})
    if not doc:
        return {}
    return {attr: doc[attr] for attr in ROBBO_KEPT_ATTRS if attr in doc}


def copied_attrs(asset):
    """Robbo attributes of a listed asset document, for copying it into another course."""
    return {attr: asset[attr] for attr in ROBBO_KEPT_ATTRS if attr in asset}


def project_fields():
    """Extra fields for the listing ``$project`` stage, so sorting by name keeps them."""
    return {attr: 1 for attr in ROBBO_KEPT_ATTRS}


def import_attrs(store, asset_key, policy_ele):
    """Restore Robbo attributes of an imported file from its ``policies/assets.json`` entry."""
    attrs = {
        attr: policy_ele[attr]
        for attr in ROBBO_KEPT_ATTRS
        if isinstance(policy_ele.get(attr), str)
    }
    if attrs:
        store.set_attrs(asset_key, attrs)


def effective_folder(asset):
    """
    Folder shown in «Файлы»: the stored label, or the ``static/`` subdirectory of an imported course.

    A stored empty string means "explicitly no folder" and wins over the import path.
    """
    folder = asset.get(ROBBO_FOLDER_ATTR)
    if isinstance(folder, str):
        return folder
    import_path = asset.get('import_path') or ''
    if '/' in import_path and not import_path.startswith(SEED_SKIPPED_PREFIXES):
        return os.path.dirname(import_path)
    return ''
