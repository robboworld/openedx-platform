# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of the Robbo Open edX distribution. See NOTICE at repository root.

"""
Course cover URLs with the file's md5 in them.

The catalog, «Мои курсы» and the course about page show the course image and its thumbnails
from ``CourseOverview``. With plain ``/asset-v1:…`` URLs, browsers kept a replaced cover for the
whole ``CourseAssetCacheTtlConfig`` TTL (1 hour, ``robbo_enable_course_asset_cache``), even after
a publish, and the thumbnails were not regenerated at all until the next publish.

Here the overview stores ``/assets/courseware/v1/<md5>/asset-v1:…``, the same versioned form lesson
images get from ``StaticContent.get_canonicalized_asset_path``: a new file is a new URL. Replacing
the cover or banner in «Файлы» rebuilds the overview at once (``robbo_asset_uploads.py``).
"""

import logging

from opaque_keys import InvalidKeyError
from xmodule.assetstore.assetmgr import AssetManager
from xmodule.contentstore.content import StaticContent
from xmodule.exceptions import NotFoundError
from xmodule.modulestore.exceptions import ItemNotFoundError

log = logging.getLogger(__name__)

COVER_FIELDS = ('course_image', 'banner_image')


def versioned_asset_url(url):
    """``url`` with the asset's md5 when it is a stored course asset; anything else unchanged."""
    if not url or not url.startswith(('/asset-v1:', '/c4x/')):
        return url
    try:
        asset_key = StaticContent.get_location_from_path(url)
        content = AssetManager.find(asset_key, as_stream=True)
    except (InvalidKeyError, ItemNotFoundError, NotFoundError):
        return url
    digest = getattr(content, 'content_digest', None)
    if not digest:
        return url
    return StaticContent.add_version_to_asset_path(url, digest)


def is_course_cover(course, asset_key):
    """True when ``asset_key`` is the file of the course image or banner of ``course``."""
    for field in COVER_FIELDS:
        name = getattr(course, field, None)
        if name and StaticContent.compute_location(asset_key.course_key, name).block_id == asset_key.block_id:
            return True
    return False


def refresh_overview_for_cover(course_key, asset_key):
    """
    Rebuild the course's ``CourseOverview`` (URLs and thumbnails) when ``asset_key`` is its cover.

    Called after an upload wrote ``asset_key``; never fails the upload. Returns whether it rebuilt.
    """
    # pylint: disable=import-outside-toplevel
    from xmodule.modulestore.django import modulestore

    from .models import CourseOverview

    try:
        course = modulestore().get_course(course_key)
        if course is None or not is_course_cover(course, asset_key):
            return False
        CourseOverview.load_from_module_store(course_key)
    except Exception:  # pylint: disable=broad-except
        log.exception('Robbo: could not refresh the course overview of %s after %s', course_key, asset_key)
        return False
    log.info('Robbo: course overview of %s rebuilt after its cover %s was replaced', course_key, asset_key)
    return True
