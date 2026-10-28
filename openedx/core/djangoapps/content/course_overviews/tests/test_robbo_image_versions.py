# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of the Robbo Open edX distribution. See NOTICE at repository root.

"""Tests for md5-versioned course cover URLs (robbo_image_versions.py)."""

import hashlib
from io import BytesIO

from PIL import Image

from xmodule.contentstore.content import StaticContent
from xmodule.contentstore.django import contentstore
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory

from ..models import CourseOverview, CourseOverviewImageConfig
from ..robbo_image_versions import refresh_overview_for_cover, versioned_asset_url


class RobboCoverVersionsTestCase(ModuleStoreTestCase):
    """The overview stores cover URLs with the file's md5; a replaced cover rebuilds it."""
    ENABLED_SIGNALS = ['course_published']

    def setUp(self):
        CourseOverviewImageConfig.objects.all().delete()
        CourseOverviewImageConfig.objects.create(
            enabled=True, small_width=200, small_height=100, large_width=400, large_height=200,
        )
        super().setUp()
        self.course = CourseFactory.create(course_image='cover.png')

    def _save_cover(self, color):
        """Save ``cover.png`` of ``color`` under the course image's key; returns its md5."""
        buff = BytesIO()
        Image.new('RGB', (800, 400), color).save(buff, format='PNG')
        data = buff.getvalue()
        key = StaticContent.compute_location(self.course.id, 'cover.png')
        contentstore().save(StaticContent(key, 'cover.png', 'image/png', data))
        return key, hashlib.md5(data).hexdigest()

    def _overview(self):
        self.clear_caches()
        return CourseOverview.objects.select_related('image_set').get(id=self.course.id)

    def test_plain_urls_unchanged(self):
        assert versioned_asset_url('') == ''
        assert versioned_asset_url('/static/images/no_course_image.png') == '/static/images/no_course_image.png'
        missing = StaticContent.serialize_asset_key_with_slash(
            StaticContent.compute_location(self.course.id, 'missing.png')
        )
        assert versioned_asset_url(missing) == missing

    def test_stored_asset_gets_md5(self):
        key, md5 = self._save_cover('red')
        url = StaticContent.serialize_asset_key_with_slash(key)
        assert versioned_asset_url(url) == StaticContent.add_version_to_asset_path(url, md5)

    def test_file_without_custom_md5_uses_gridfs_md5(self):
        """Files uploaded before ``custom_md5`` existed keep only the GridFS md5 (xmodule mongo.py)."""
        key, md5 = self._save_cover('red')
        store = contentstore()
        content_id, __ = store.asset_db_key(key)
        store.fs_files.update_one({'_id': content_id}, {'$unset': {'custom_md5': 1}, '$set': {'md5': md5}})
        url = StaticContent.serialize_asset_key_with_slash(key)
        assert versioned_asset_url(url) == StaticContent.add_version_to_asset_path(url, md5)

    def test_replaced_cover_rebuilds_overview(self):
        key, md5_red = self._save_cover('red')
        assert refresh_overview_for_cover(self.course.id, key)
        before = self._overview()
        assert f'/{md5_red}/' in before.course_image_url
        small_before = before.image_set.small_url
        assert StaticContent.is_versioned_asset_path(small_before)
        assert small_before.endswith('cover-png-200x100.jpg')

        key, md5_blue = self._save_cover('blue')
        assert refresh_overview_for_cover(self.course.id, key)
        after = self._overview()
        assert f'/{md5_blue}/' in after.course_image_url
        assert after.image_set.small_url != small_before
        assert after.image_set.small_url.endswith('cover-png-200x100.jpg')

    def test_other_asset_leaves_overview(self):
        self._save_cover('red')
        other = StaticContent.compute_location(self.course.id, 'slide.png')
        assert not refresh_overview_for_cover(self.course.id, other)
