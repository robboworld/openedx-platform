# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of the Robbo Open edX distribution. See NOTICE at repository root.

"""«Заменить файл» on the course cover gives the overview a new versioned URL without a publish."""

from io import BytesIO
from unittest import mock

from PIL import Image

from cms.djangoapps.contentstore.tests.utils import CourseTestCase
from cms.djangoapps.contentstore.utils import reverse_course_url
from xmodule.modulestore.tests.django_utils import TEST_DATA_SPLIT_MODULESTORE
from xmodule.modulestore.tests.factories import CourseFactory

REFRESH = 'cms.djangoapps.contentstore.robbo_asset_uploads.refresh_overview_for_cover'


class RobboCoverUploadTestCase(CourseTestCase):
    """The upload hook asks for an overview refresh only when it wrote a file."""
    MODULESTORE = TEST_DATA_SPLIT_MODULESTORE

    def setUp(self):
        super().setUp()
        self.course = CourseFactory(default_store='split', course_image='cover.png')
        self.url = reverse_course_url('assets_handler', self.course.id)

    def _post(self, color, name='cover.png', **extra):
        buff = BytesIO()
        Image.new('RGB', (60, 30), color).save(buff, 'PNG')
        buff.seek(0)
        buff.name = name
        return self.client.post(self.url, {'file': buff, **extra})

    def test_created_and_replaced_refresh(self):
        with mock.patch(REFRESH) as refresh:
            assert self._post('red').status_code == 200
            assert self._post('blue', robbo_on_conflict='replace').status_code == 200
        assert refresh.call_count == 2
        course_key, asset_key = refresh.call_args.args
        assert course_key == self.course.id
        assert asset_key.block_id == 'cover.png'

    def test_reused_and_renamed_do_not_refresh(self):
        self._post('red')
        with mock.patch(REFRESH) as refresh:
            self._post('red')  # same content: the existing file is reused
            resp = self._post('green')  # another content without replace: cover-2.png
        assert resp.json()['robbo_upload']['status'] == 'renamed'
        refresh.assert_not_called()
