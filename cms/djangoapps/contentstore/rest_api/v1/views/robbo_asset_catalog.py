# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (course files catalog). See NOTICE at repository root.
"""
Studio API for the «Файлы» catalog: upload pre-flight and moving files between author folders.
"""

import logging

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from cms.djangoapps.contentstore.api import course_author_access_required
from cms.djangoapps.contentstore.robbo_asset_folders import move_assets
from cms.djangoapps.contentstore.robbo_asset_uploads import check_uploads
from openedx.core.lib.api.view_utils import DeveloperErrorViewMixin, view_auth_classes

log = logging.getLogger(__name__)

MAX_ITEMS = 500


def _list_param(request, name):
    value = request.data.get(name)
    return value if isinstance(value, list) else None


@view_auth_classes(is_authenticated=True)
class AssetUploadCheckView(DeveloperErrorViewMixin, APIView):
    """
    Course team only.

    POST /api/contentstore/v1/robbo/assets/{course_id}/upload-check
        {"files": [{"name": "Слайд13.JPG", "size": 12345}, …]}
        → {"files": [{"name", "asset_name", "exists", "suggested_name",
                      "existing": null | {"id", "display_name", "file_size", "same_size",
                                          "robbo_folder", "usage_locations"}}, …]}
    """

    @course_author_access_required
    def post(self, request: Request, course_key):
        files = _list_param(request, 'files')
        if files is None or len(files) > MAX_ITEMS:
            raise self.api_error(status.HTTP_400_BAD_REQUEST, 'Expected "files": [{name, size}].', 'invalid_files')
        files = [item for item in files if isinstance(item, dict)]
        return Response({'files': check_uploads(course_key, files)})


@view_auth_classes(is_authenticated=True)
class AssetFolderMoveView(DeveloperErrorViewMixin, APIView):
    """
    Course team only.

    POST /api/contentstore/v1/robbo/assets/{course_id}/folders/move
        {"asset_ids": ["asset-v1:…", …], "folder": "Урок 3"}   ("" — no folder)
        → {"moved": [asset ids], "folder": normalized folder name}

    Renaming a folder is moving all its files to the new name; deleting it is moving them to "".
    """

    @course_author_access_required
    def post(self, request: Request, course_key):
        asset_ids = _list_param(request, 'asset_ids')
        folder = request.data.get('folder', '')
        if asset_ids is None or len(asset_ids) > MAX_ITEMS or not isinstance(folder, str):
            raise self.api_error(
                status.HTTP_400_BAD_REQUEST, 'Expected "asset_ids": [...] and "folder": "".', 'invalid_move',
            )
        moved, folder = move_assets(course_key, asset_ids, folder)
        log.info('Robbo: %s moved %d files of %s to folder %r', request.user.username, len(moved), course_key, folder)
        return Response({'moved': moved, 'folder': folder})
