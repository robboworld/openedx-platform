# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (certificate designs). See NOTICE at repository root.
"""
Certificate designs available to courses.

Two kinds:

* ``theme`` — Mako partial ``robbo-theme/lms/templates/certificates/designs/<id>.html``
  (developers). Optional header lines ``## title: …`` / ``## description: …`` / ``## hours: yes`` (the design
  prints the course volume, so Studio shows «Объём курса, часов») and a thumbnail
  ``robbo-theme/lms/static/images/certificates/designs/<id>.png``.
* ``uploaded`` — ``CertificateDesign`` rows created by platform staff in Studio
  (background image + positioned fields), rendered by ``_robbo-design-uploaded.html``.

A course stores the chosen id in ``cert_html_view_overrides[DESIGN_OVERRIDE_KEY]``
(Advanced Settings), so it reaches the LMS certificate context with no extra plumbing.
"""

import re
from pathlib import Path

from django.conf import settings
from django.core.files.storage import default_storage

from openedx.core.djangoapps.theming.helpers import get_theme_base_dir

DESIGN_OVERRIDE_KEY = 'robbo_certificate_template'
DEFAULT_DESIGN = 'olympiad'  # courses: Scratch Olympiad sheet in English (online: olympiad, skill: robbo)
PREVIEW_QUERY_PARAM = 'robbo_design'

KIND_THEME = 'theme'
KIND_UPLOADED = 'uploaded'

# Who made the design: the dev team (theme partials, designs flagged is_custom) or staff in the builder
ORIGIN_CUSTOM = 'custom'
ORIGIN_BUILDER = 'builder'

_THEME = 'robbo-theme'
_DESIGN_ID_RE = re.compile(r'^[a-z0-9][a-z0-9_-]{0,63}$')
_HEADER_RE = re.compile(r'^##\s*(title|description|hours)\s*:\s*(.+?)\s*$')


def absolute_media_url(name):
    """URL of a stored file that also works from Studio (another host)."""
    url = default_storage.url(name)
    return url if url.startswith(('http://', 'https://', '//')) else f'{settings.LMS_ROOT_URL}{url}'


def _theme_lms_dir():
    base = get_theme_base_dir(_THEME, suppress_error=True)
    return Path(base) / _THEME / 'lms' if base else None


def _read_header(path):
    meta = {}
    with open(path, encoding='utf-8') as template:
        for line in template:
            if not line.startswith('##'):
                break
            match = _HEADER_RE.match(line)
            if match:
                meta[match.group(1)] = match.group(2)
    return meta


def _theme_designs():
    lms_dir = _theme_lms_dir()
    templates_dir = lms_dir / 'templates' / 'certificates' / 'designs' if lms_dir else None
    if not templates_dir or not templates_dir.is_dir():
        return []

    designs = []
    for path in templates_dir.glob('*.html'):
        design_id = path.stem
        if not _DESIGN_ID_RE.match(design_id):
            continue
        meta = _read_header(path)
        image = lms_dir / 'static' / 'images' / 'certificates' / 'designs' / f'{design_id}.png'
        designs.append({
            'id': design_id,
            'kind': KIND_THEME,
            'origin': ORIGIN_CUSTOM,
            'uses_hours': meta.get('hours', '').lower() in ('yes', 'true', '1'),
            'title': meta.get('title') or design_id,
            'description': meta.get('description', ''),
            'preview_image_url': (
                f'{settings.LMS_ROOT_URL}/static/{_THEME}/images/certificates/designs/{design_id}.png'
                if image.is_file() else None
            ),
        })
    return designs


def uploaded_design_payload(design):
    return {
        'id': design.slug,
        'kind': KIND_UPLOADED,
        'origin': ORIGIN_CUSTOM if design.is_custom else ORIGIN_BUILDER,
        # Studio shows the «Объём курса, часов» setting only for designs that print it
        'uses_hours': any(field.get('type') == 'hours' for field in design.fields or []),
        'title': design.title,
        'description': design.description,
        'preview_image_url': absolute_media_url(design.background.name) if design.background else None,
        'background_url': absolute_media_url(design.background.name) if design.background else None,
        'fields': design.fields,
        'is_active': design.is_active,
    }


def _uploaded_designs():
    from .models import CertificateDesign  # pylint: disable=import-outside-toplevel
    return [uploaded_design_payload(design) for design in CertificateDesign.objects.filter(is_active=True)]


def list_designs():
    """All selectable designs, default first, then by title."""
    designs = _theme_designs() + _uploaded_designs()
    designs.sort(key=lambda design: (design['id'] != DEFAULT_DESIGN, design['title'].lower()))
    return designs


def get_design(value):
    """Design dict for ``value`` (a stored or previewed id), falling back to DEFAULT_DESIGN."""
    design_id = str(value or '').strip().lower()
    designs = {design['id']: design for design in list_designs()}
    return designs.get(design_id) or designs.get(DEFAULT_DESIGN) or {
        'id': DEFAULT_DESIGN, 'kind': KIND_THEME, 'origin': ORIGIN_CUSTOM, 'uses_hours': False,
        'title': DEFAULT_DESIGN, 'description': '',
    }


def resolve_design(value):
    return get_design(value)['id']


def design_ids():
    return {design['id'] for design in list_designs()}
