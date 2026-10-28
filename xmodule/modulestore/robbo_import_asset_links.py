# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (course import). See NOTICE at repository root.
"""
Full links to course files in imported content.

A course exported from another instance keeps links with that instance's host:
``https://lms2.robbo.world/asset-v1:<course>+type@asset+block@<name>``, also ``...+block/<name>`` and
``/assets/courseware/v1/<md5>/asset-v1:...``. The upstream import (``rewrite_nonportable_content_links``)
only rewrites host-less links to the exported course that start right after a quote, so such links keep
loading files from the old server. ``ImportAssetLinks`` rewrites them in every string of a block's
content and settings fields; dicts and lists are walked, not their JSON text.

* The link points at the exported course or the course being imported into, and the import brings a file
  with this name (``static/`` of the archive) or the course already has it:

  - in the ``data`` string (html, problem, about, course info) it becomes ``/static/<name>``: the LMS
    expands it to ``/assets/courseware/v1/<md5>/...``, which is cached for a year;
  - in other fields (certificate signatures, video handout, PDF textbooks) it becomes the new course's
    asset path ``/asset-v1:<new course>+type@asset+block@<name>``: Studio editors, the certificate
    template and ``robbo_signature_assets`` use the value as is and do not expand ``/static/``.

* Otherwise only the host is dropped: ``/asset-v1:...`` is served by whichever instance shows the course.
  Links to other courses never become ``/static/``: the file may differ from the one with the same name here.

Host-less links (``/asset-v1:...``, ``/assets/courseware/...``) to the course itself and to a file it has
are rewritten the same way; other host-less links are left as they are.
"""

import logging
import os
import re
from urllib.parse import unquote

from opaque_keys import InvalidKeyError
from opaque_keys.edx.locator import CourseLocator
from xblock.fields import Scope

from xmodule.contentstore.content import StaticContent
from xmodule.modulestore.django import ASSET_IGNORE_REGEX

log = logging.getLogger(__name__)

# ``https://host``, ``//host`` or nothing, then an optional versioned prefix and the asset path.
# The look-behind keeps host-less matches out of other URLs (``/static/asset-v1:...``, ``host/asset-v1:...``).
ASSET_LINK_RE = re.compile(
    r'(?<![\w/.:%\-])'
    r'(?P<host>(?:https?:)?//[A-Za-z0-9.\-]+(?::\d+)?)?'
    r'(?P<version>/assets/courseware/(?:v\d/)?[a-f0-9]{32})?'
    r'/asset-v1:(?P<course>[\w\-~.]+\+[\w\-~.]+\+[\w\-~.]+)\+type@asset\+block[@/](?P<name>[\w\-~.:%]+)'
)

# String fields whose links the LMS and Studio expand from ``/static/<name>``.
STATIC_LINK_FIELDS = ('data',)


def _course_triple(course_key):
    return (course_key.org, course_key.course, course_key.run)


class ImportAssetLinks:
    """
    Rewrites full links to course files in the fields of blocks imported into ``dest_course_id``.

    ``static_dir`` is the archive's ``static/`` folder and ``content_store`` the store the files go to;
    without them no file is known and links only lose their host.
    """

    def __init__(self, source_course_id, dest_course_id, static_dir=None, content_store=None):
        self.dest_course_id = dest_course_id
        self.own_courses = {
            _course_triple(key) for key in (source_course_id, dest_course_id)
            if isinstance(key, CourseLocator)
        }
        self.content_store = content_store
        self.static_names = self._static_names(static_dir) if static_dir else set()
        self._known = {}
        self.rewritten = 0

    @staticmethod
    def _static_names(static_dir):
        """Asset names of the archive's files, as ``StaticContentImporter`` names them."""
        names = set()
        for dirname, _, filenames in os.walk(static_dir):
            for filename in filenames:
                if re.match(ASSET_IGNORE_REGEX, filename):
                    continue
                subpath = os.path.relpath(os.path.join(dirname, filename), static_dir)
                names.add(subpath.replace(os.sep, '/').replace('/', '_'))
        return names

    def _has_file(self, name):
        """True when the new course gets (or already has) a file with this asset name."""
        if name not in self._known:
            self._known[name] = any(
                candidate in self.static_names or self._in_store(candidate)
                for candidate in dict.fromkeys((name, unquote(name)))
            )
        return self._known[name]

    def _in_store(self, name):
        if self.content_store is None:
            return False
        try:
            asset_key = self.dest_course_id.make_asset_key('asset', name)
            return self.content_store.find(asset_key, throw_on_not_found=False, as_stream=True) is not None
        except InvalidKeyError:
            return False
        except Exception:  # pylint: disable=broad-except
            log.exception('robbo asset links: could not look up %s in %s', name, self.dest_course_id)
            return False

    def _is_own_course(self, course):
        try:
            course_key = CourseLocator.from_string(f'course-v1:{course}')
        except InvalidKeyError:
            return False
        return _course_triple(course_key) in self.own_courses

    def rewrite_text(self, text, to_static):
        """``text`` with its asset links rewritten; ``to_static`` allows ``/static/<name>``."""
        if 'asset-v1:' not in text:
            return text

        def substitute(match):
            name = match.group('name')
            if self._is_own_course(match.group('course')) and self._has_file(name):
                if to_static:
                    new = f'/static/{name}'
                else:
                    new = StaticContent.serialize_asset_key_with_slash(
                        self.dest_course_id.make_asset_key('asset', name)
                    )
            elif match.group('host'):
                new = match.group(0)[len(match.group('host')):]
            else:
                return match.group(0)
            if new != match.group(0):
                self.rewritten += 1
            return new

        new_text = ASSET_LINK_RE.sub(substitute, text)
        return text if new_text == text else new_text

    def rewrite_value(self, value, to_static=False):
        """Copy of a field value with links rewritten in its strings; the value itself when nothing changed."""
        if isinstance(value, str):
            return self.rewrite_text(value, to_static)
        if isinstance(value, dict):
            items = {key: self.rewrite_value(item) for key, item in value.items()}
            if any(items[key] is not item for key, item in value.items()):
                return items
            return value
        if isinstance(value, (list, tuple)):
            items = [self.rewrite_value(item) for item in value]
            if any(new is not old for new, old in zip(items, value)):
                return type(value)(items)
            return value
        return value

    def rewrite_fields(self, block, fields):
        """Rewrite the content and settings values of ``fields``, the import values of ``block``."""
        for field_name, value in fields.items():
            field = block.fields.get(field_name)
            if field is None or field.scope not in (Scope.content, Scope.settings):
                continue
            to_static = field_name in STATIC_LINK_FIELDS and isinstance(value, str)
            fields[field_name] = self.rewrite_value(value, to_static)
        return fields
