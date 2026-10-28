# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (course import). See NOTICE at repository root.
"""
Course import rewrites full links to course files (xmodule/modulestore/robbo_import_asset_links.py).
"""

import copy
import json
import os
import shutil
import tempfile
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.test.utils import override_settings
from opaque_keys.edx.keys import CourseKey

from xmodule.contentstore.django import contentstore
from xmodule.modulestore.django import modulestore
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.xml_importer import import_course_from_xml

TEST_DATA_CONTENTSTORE = copy.deepcopy(settings.CONTENTSTORE)
TEST_DATA_CONTENTSTORE['DOC_STORE_CONFIG']['db'] = 'test_xcontent_%s' % uuid4().hex

DEST = CourseKey.from_string('course-v1:Robbo+DEST+2026')
LMS2 = 'https://lms2.robbo.world/asset-v1:Robbo+SRC+2025+type@asset+block@'
ONLINE = 'https://online.robbo.ru/asset-v1:Robbo+SRC+2025+type@asset+block@'
MD5 = '0123456789abcdef0123456789abcdef'

OLX = {
    'course.xml': '<course org="Robbo" course="SRC" url_name="2025"/>',
    'course/2025.xml': (
        '<course display_name="Ссылки"><chapter url_name="ch" display_name="Раздел">'
        '<sequential url_name="seq"><vertical url_name="vert">'
        '<html url_name="pic"/><problem url_name="prob"/><video url_name="vid"/>'
        '</vertical></sequential></chapter></course>'
    ),
    'html/pic.xml': '<html filename="pic" display_name="Картинки"/>',
    'html/pic.html': (
        f'<p><img src="{LMS2}pic.png"/></p>'
        f'<p><img src="https://online.robbo.ru/assets/courseware/v1/{MD5}/'
        'asset-v1:Robbo+SRC+2025+type@asset+block/pic.png"/></p>'
        '<p><img src="https://lms2.robbo.world/asset-v1:Robbo+OLD+2024+type@asset+block@pic.png"/></p>'
        '<p><img src="https://test.lms.robbo.ru/asset-v1:Robbo+SRC+2025+type@asset+block@missing.png"/></p>'
        '<p><a href="https://robbo.ru/">robbo.ru</a></p>'
    ),
    'problem/prob.xml': (
        f'<problem display_name="Задача"><p><img src="{ONLINE}pic.png"/></p>'
        '<stringresponse answer="1"><textline/></stringresponse></problem>'
    ),
    'video/vid.xml': f'<video display_name="Видео"><handout src="{LMS2}handout.pdf"/></video>',
    'about/overview.html': f'<p><img src="{ONLINE.replace("block@", "block/")}pic.png"/></p>',
    'policies/2025/policy.json': json.dumps({'course/2025': {
        'certificates': {'certificates': [{
            'id': 1, 'name': 'Сертификат', 'version': 1, 'is_active': True,
            'signatories': [{'id': 1, 'name': 'А', 'title': 'Б', 'signature_image_path': f'{LMS2}sig.png'}],
        }]},
        'pdf_textbooks': [{'tab_title': 'Учебник', 'url': f'{ONLINE}handout.pdf', 'chapters': [
            {'title': 'Глава', 'url': f'{LMS2}handout.pdf'},
        ]}],
    }}),
    'policies/2025/grading_policy.json': '{}',
    'static/pic.png': 'png',
    'static/sig.png': 'png',
    'static/handout.pdf': 'pdf',
}


@override_settings(CONTENTSTORE=TEST_DATA_CONTENTSTORE, SEARCH_ENGINE=None)
class ImportAssetLinksTest(ModuleStoreTestCase):
    """An OLX course from another instance comes in without that instance's host in file links."""

    def setUp(self):
        super().setUp()
        patcher = patch('openedx.core.djangoapps.content.block_structure.tasks.update_course_in_cache_v2')
        patcher.start()
        self.addCleanup(patcher.stop)
        self.data_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.data_dir)
        for subpath, text in OLX.items():
            full_path = os.path.join(self.data_dir, 'olx', subpath)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(text)

    def import_course(self):
        store = modulestore()
        import_course_from_xml(
            store, self.user.id, self.data_dir, ['olx'],
            static_content_store=contentstore(), target_id=DEST, create_if_not_present=True,
        )
        return store

    def test_links_are_rewritten(self):
        store = self.import_course()

        html = store.get_item(DEST.make_usage_key('html', 'pic')).data
        assert html.count('src="/static/pic.png"') == 2
        # another course's file and a file the course has no copy of only lose the host
        assert 'src="/asset-v1:Robbo+OLD+2024+type@asset+block@pic.png"' in html
        assert 'src="/asset-v1:Robbo+SRC+2025+type@asset+block@missing.png"' in html
        assert 'href="https://robbo.ru/"' in html
        for host in ('lms2.robbo.world', 'online.robbo.ru', 'test.lms.robbo.ru'):
            assert host not in html

        assert 'src="/static/pic.png"' in store.get_item(DEST.make_usage_key('problem', 'prob')).data
        assert 'src="/static/pic.png"' in store.get_item(DEST.make_usage_key('about', 'overview')).data

        handout = '/asset-v1:Robbo+DEST+2026+type@asset+block@handout.pdf'
        assert store.get_item(DEST.make_usage_key('video', 'vid')).handout == handout

        course = store.get_course(DEST)
        signatory = course.certificates['certificates'][0]['signatories'][0]
        assert signatory['signature_image_path'] == '/asset-v1:Robbo+DEST+2026+type@asset+block@sig.png'
        textbook = course.pdf_textbooks[0]
        assert textbook['url'] == handout
        assert textbook['chapters'][0]['url'] == handout

    def test_reimport_keeps_links(self):
        """A second import of the same archive finds the files already in the course."""
        self.import_course()
        store = self.import_course()
        assert store.get_item(DEST.make_usage_key('html', 'pic')).data.count('src="/static/pic.png"') == 2
