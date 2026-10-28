# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (course files catalog). See NOTICE at repository root.
"""
Course file uploads that never overwrite a file silently.

Upstream saves an upload under its own name, so a second «Слайд13.JPG» from another presentation
replaces the picture in every block that already shows the first one. Here, when a file with the
same asset key already exists:

* the same content (md5) — the existing file is reused, nothing is written;
* ``robbo_on_conflict=replace`` — the file is replaced (only the «Файлы» dialog sends it);
* otherwise — the upload is saved as ``<name>-2.<ext>`` (``-3``, …).

Every client reads the asset name and URL back from the response, so editors, course settings,
certificates and textbooks get the renamed or reused file without changes.
"""

import hashlib
import logging
import os
import unicodedata

from django.conf import settings
from django.core.cache import cache
from django.utils.translation import gettext as _
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

from common.djangoapps.util.json_request import JsonResponse
from lms.djangoapps.robbo_errors.responses import robbo_error
from openedx.core.djangoapps.content.course_overviews.robbo_image_versions import refresh_overview_for_cover
from xmodule.contentstore.content import StaticContent
from xmodule.contentstore.django import contentstore
from xmodule.exceptions import NotFoundError

log = logging.getLogger(__name__)

ON_CONFLICT_PARAM = 'robbo_on_conflict'
ON_CONFLICT_REPLACE = 'replace'
LOCK_TTL = 30
MAX_SUFFIX = 99

STATUS_CREATED = 'created'
STATUS_REUSED = 'reused'
STATUS_REPLACED = 'replaced'
STATUS_RENAMED = 'renamed'


def normalize_name(name):
    """NFC, so a name typed on macOS (decomposed «й») gets the same key as one typed elsewhere."""
    return unicodedata.normalize('NFC', name or '')


def _existing_attrs(asset_key):
    try:
        return contentstore().get_attrs(asset_key)
    except NotFoundError:
        return None


def _upload_md5(upload_file):
    digest = hashlib.md5()
    for chunk in upload_file.chunks():
        digest.update(chunk)
    upload_file.seek(0)
    return digest.hexdigest()


def _stored_md5(asset_key, attrs):
    """md5 of an existing asset: Teak stores ``custom_md5``, older uploads GridFS ``md5``."""
    stored = attrs.get('custom_md5') or attrs.get('md5')
    if stored:
        return stored
    try:
        return hashlib.md5(contentstore().find(asset_key).data).hexdigest()
    except NotFoundError:
        return None


def suffixed_names(name):
    """``Слайд13-2.JPG``, ``Слайд13-3.JPG``, … — ``-`` and digits are safe in asset keys and MFE paths."""
    stem, ext = os.path.splitext(name)
    for number in range(2, MAX_SUFFIX + 1):
        yield f'{stem}-{number}{ext}'


def free_name(course_key, name, upload_md5=None):
    """
    First suffixed name that is free in the course (or already holds the same content).

    Returns ``(name, reused)``.
    """
    for candidate in suffixed_names(name):
        key = StaticContent.compute_location(course_key, candidate)
        attrs = _existing_attrs(key)
        if attrs is None:
            return candidate, False
        if upload_md5 and _stored_md5(key, attrs) == upload_md5:
            return candidate, True
    stem, ext = os.path.splitext(name)
    return f'{stem}-{(upload_md5 or hashlib.md5(name.encode()).hexdigest())[:8]}{ext}', False


def _lock(asset_key):
    lock_key = 'robbo:asset-upload:' + hashlib.md5(str(asset_key).encode()).hexdigest()
    return lock_key, cache.add(lock_key, 1, LOCK_TTL)


def resolve_upload(request, course_key, upload_file):
    """
    Decide what to do with ``upload_file``: ``(status, asset_key_to_reuse_or_None, original_name)``.

    Renames ``upload_file`` in place when it has to be saved under a new name.
    """
    original_name = normalize_name(upload_file.name)
    upload_file.name = original_name
    asset_key = StaticContent.compute_location(course_key, original_name)
    attrs = _existing_attrs(asset_key)
    if attrs is None:
        return STATUS_CREATED, None, original_name

    upload_md5 = _upload_md5(upload_file)
    if _stored_md5(asset_key, attrs) == upload_md5:
        return STATUS_REUSED, asset_key, original_name
    if request.POST.get(ON_CONFLICT_PARAM) == ON_CONFLICT_REPLACE:
        return STATUS_REPLACED, None, original_name

    name, reused = free_name(course_key, original_name, upload_md5)
    if reused:
        return STATUS_REUSED, StaticContent.compute_location(course_key, name), original_name
    upload_file.name = name
    return STATUS_RENAMED, None, original_name


def _asset_response(course_key, asset_key, status, original_name):
    """Upstream upload response for ``asset_key`` read back from the store, with usage and folder."""
    # pylint: disable=import-outside-toplevel
    from .asset_storage_handlers import get_asset_json
    from . import robbo_asset_folders, robbo_asset_usage

    readback = contentstore().find(asset_key, as_stream=True)
    usage_locations = robbo_asset_usage.get_asset_usage_path(
        course_key, [{'asset_key': asset_key}],
    ).get(str(asset_key), [])
    asset_json = get_asset_json(
        readback.name,
        readback.content_type,
        readback.last_modified_at,
        readback.location,
        readback.thumbnail_location,
        getattr(readback, 'locked', False),
        course_key,
        getattr(readback, 'length', None),
        usage_locations,
    )
    asset_json.update(robbo_asset_folders.asset_json_extras(contentstore().get_attrs(asset_key)))
    return JsonResponse({
        'asset': asset_json,
        'msg': _('Upload completed'),
        'robbo_upload': {
            'status': status,
            'name': readback.name,
            'original_name': original_name,
        },
    })


@require_POST
@ensure_csrf_cookie
@login_required
def upload_asset(request, course_key):
    """Drop-in for upstream ``_upload_asset``: same response, plus ``robbo_upload`` and ``robbo_folder``."""
    # pylint: disable=import-outside-toplevel
    from .asset_storage_handlers import _get_error_if_course_does_not_exist, update_course_run_asset
    from .exceptions import AssetSizeTooLargeException
    from . import robbo_asset_folders

    course_exists_error = _get_error_if_course_does_not_exist(course_key)
    if course_exists_error is not None:
        return course_exists_error
    if course_key.deprecated:
        return JsonResponse({'error': 'Uploading assets for the legacy course is not available.'}, status=400)

    upload_file = request.FILES['file']
    lock_key, locked = _lock(StaticContent.compute_location(course_key, normalize_name(upload_file.name)))
    try:
        status, reuse_key, original_name = resolve_upload(request, course_key, upload_file)
        if not locked and status == STATUS_CREATED:
            # Another upload of the same name is in flight: keep both instead of racing.
            name, _reused = free_name(course_key, original_name)
            upload_file.name = name
            status = STATUS_RENAMED
        if status == STATUS_REUSED:
            return _asset_response(course_key, reuse_key, status, original_name)
        try:
            content = update_course_run_asset(course_key, upload_file)
        except AssetSizeTooLargeException as exception:
            # The human text with a code and number (lms/djangoapps/robbo_errors), not the English sentence.
            return robbo_error(
                request, 'UPLOAD-SIZE', 413, developer_message=str(exception),
                limit=settings.MAX_ASSET_UPLOAD_FILE_SIZE_IN_MB,
            )
        robbo_asset_folders.apply_upload_folder(request, content.location, created=status != STATUS_REPLACED)
        if status in (STATUS_CREATED, STATUS_REPLACED):
            # A new file under the cover's name: new versioned URLs and thumbnails without a publish.
            refresh_overview_for_cover(course_key, content.location)
        if status != STATUS_CREATED:
            log.info('Robbo asset upload %s: %s -> %s (%s)', course_key, original_name, content.name, status)
        return _asset_response(course_key, content.location, status, original_name)
    finally:
        if locked:
            cache.delete(lock_key)


def check_uploads(course_key, files):
    """
    Pre-flight for the «Файлы» upload dialog.

    ``files`` — ``[{'name': …, 'size': …}]``. For each one says whether a file with the same asset key
    exists, where it is used and which name «Сохранить как копию» would get.
    """
    # pylint: disable=import-outside-toplevel
    from . import robbo_asset_folders, robbo_asset_usage

    result = []
    existing_keys = []
    for item in files:
        name = normalize_name(str(item.get('name') or ''))
        if not name:
            continue
        asset_key = StaticContent.compute_location(course_key, name)
        attrs = _existing_attrs(asset_key)
        entry = {
            'name': name,
            'asset_name': asset_key.block_id,
            'exists': attrs is not None,
            'existing': None,
            'suggested_name': None,
        }
        if attrs is not None:
            existing_keys.append(asset_key)
            entry['existing'] = {
                'id': str(asset_key),
                'display_name': attrs.get('displayname', name),
                'file_size': attrs.get('length'),
                'same_size': item.get('size') is not None and attrs.get('length') == item.get('size'),
                **robbo_asset_folders.asset_json_extras(attrs),
            }
            entry['suggested_name'] = free_name(course_key, name)[0]
        result.append(entry)
    if existing_keys:
        usage = robbo_asset_usage.get_asset_usage_path(course_key, [{'asset_key': key} for key in existing_keys])
        for entry in result:
            if entry['existing']:
                entry['existing']['usage_locations'] = usage.get(entry['existing']['id'], [])
    return result
