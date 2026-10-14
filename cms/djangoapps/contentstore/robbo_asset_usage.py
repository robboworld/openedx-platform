# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (course files catalog). See NOTICE at repository root.
"""
Where course files (assets) are used: one pass over the whole course.

Upstream only looks at ``data`` of the direct children of units, so the course card image, certificate
signatures, ORA prompts, pages, the course about page and nested blocks show up as "not used".
Here every content/settings field of every block (draft and published) is scanned once per course
structure version and indexed by asset name, so a reference counts whatever host, course run or
URL form (``/static/…``, ``/asset-v1:…``, versioned ``/assets/courseware/…``, ``/c4x/…``) it uses.

Entries keep the upstream ``display_location``/``url`` shape; Robbo details live under ``robbo``.
"""

import hashlib
import html
import json
import logging
import re
import unicodedata
from urllib.parse import unquote

from django.core.cache import cache
from django.utils.translation import gettext as _
from opaque_keys.edx.locator import AssetLocator
from xblock.fields import Scope

from xmodule.modulestore import ModuleStoreEnum
from xmodule.modulestore.django import modulestore

log = logging.getLogger(__name__)

# Bump when the entry format changes: cached indexes of the old format are then ignored.
SCHEMA_V = 2
CACHE_TTL = 60 * 60

# Blocks that live outside the course tree (no parent chain to the course root) but are course content.
DETACHED_KINDS = {
    'about': 'about',
    'static_tab': 'page',
}
COURSE_INFO_KINDS = {
    'updates': 'updates',
    'handouts': 'handouts',
}
# Order of course-level kinds in the usage list (blocks follow, in outline order).
KIND_ORDER = (
    'course_image', 'banner_image', 'video_thumbnail', 'about', 'certificate', 'textbook',
    'page', 'updates', 'handouts', 'course_settings', 'block',
)
COURSE_IMAGE_FIELDS = (
    ('course_image', 'course_image'),
    ('banner_image', 'banner_image'),
    ('video_thumbnail_image', 'video_thumbnail'),
)
COURSE_SPECIAL_FIELDS = {'course_image', 'banner_image', 'video_thumbnail_image', 'certificates',
                         'pdf_textbooks', 'html_textbooks'}
SKIPPED_FIELDS = {'children', 'parent', 'xml_attributes'}

_STOP = r'\s"\'<>()\\`'
STATIC_RE = re.compile(r'/static/([^' + _STOP + r']+)')
ASSET_RE = re.compile(
    r'asset-v1:([^+' + _STOP + r'/]+)\+([^+' + _STOP + r'/]+)\+([^+' + _STOP + r'/]+)'
    r'\+type@asset\+block[@/]([^' + _STOP + r'?#]+)'
)
C4X_RE = re.compile(r'/c4x/([^/' + _STOP + r']+)/([^/' + _STOP + r']+)/asset/([^' + _STOP + r'?#]+)')
_TAIL_RE = re.compile(r'[?#"\'<>\s].*\Z', re.S)


def asset_names(raw):
    """
    All the asset key names a referenced path may stand for: raw and unquoted, as typed and NFC
    (new uploads are NFC; files uploaded earlier from macOS may still have a decomposed key).
    """
    raw = _TAIL_RE.sub('', html.unescape(raw))
    names = set()
    for candidate in {raw, unquote(raw)}:
        for variant in {candidate, unicodedata.normalize('NFC', candidate)}:
            if variant:
                names.add(AssetLocator.clean_keeping_underscores(variant.replace('/', '_')))
    return names


def extract_refs(text):
    """
    Asset references in ``text`` as a set of ``(name, course_triple_or_None)``.

    The triple is ``ORG+COURSE+RUN`` (or ``ORG+COURSE`` for /c4x/) when the URL names a course.
    """
    refs = set()
    if not text or ('static/' not in text and 'asset' not in text and 'c4x' not in text):
        return refs
    for match in STATIC_RE.finditer(text):
        refs.update((name, None) for name in asset_names(match.group(1)))
    for match in ASSET_RE.finditer(text):
        triple = '+'.join(match.group(1, 2, 3))
        refs.update((name, triple) for name in asset_names(match.group(4)))
    for match in C4X_RE.finditer(text):
        pair = '+'.join(match.group(1, 2))
        refs.update((name, pair) for name in asset_names(match.group(3)))
    return refs


def _value_text(value):
    """A field value as searchable text: JSON strings (ORA prompts) are re-dumped without \\u escapes."""
    if value is None or isinstance(value, (bool, int, float)):
        return ''
    if isinstance(value, str):
        stripped = value.lstrip()
        if stripped[:1] in ('[', '{') and '\\u' in value:
            try:
                return json.dumps(json.loads(value), ensure_ascii=False)
            except ValueError:
                return value
        return value
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(value)


def _iter_field_texts(block, skip=()):
    """``(field_name, text)`` for every content/settings field explicitly set on ``block``."""
    for name, field in block.fields.items():
        if name in SKIPPED_FIELDS or name in skip or field.scope not in (Scope.content, Scope.settings):
            continue
        try:
            if not field.is_set_on(block):
                continue
            text = _value_text(field.read_from(block))
        except Exception:  # pylint: disable=broad-except
            continue
        if text:
            yield name, text


def _course_triple(course_key):
    return f'{course_key.org}+{course_key.course}+{course_key.run}'


def _ident(key):
    return (key.block_type, key.block_id)


def _course_url(prefix, course_key):
    return f'/{prefix}/{course_key}'


class _IndexBuilder:
    """Collects ``name -> [usage entry]`` for one course."""

    def __init__(self, course_key):
        self.course_key = course_key
        self.own = {_course_triple(course_key), f'{course_key.org}+{course_key.course}'}
        self.index = {}
        self.seen = set()

    def add_text(self, text, entry_factory, published_only=False):
        for name, triple in extract_refs(text):
            self.add(name, triple, entry_factory, published_only)

    def add_plain_name(self, value, entry_factory):
        """Fields holding a bare asset name (course card image) rather than a URL."""
        if not value or not isinstance(value, str):
            return
        refs = extract_refs(value)
        if refs:
            for name, triple in refs:
                self.add(name, triple, entry_factory)
            return
        for name in asset_names(value.strip().lstrip('/')):
            self.add(name, None, entry_factory)

    def add(self, name, triple, entry_factory, published_only=False):
        other_course = triple if triple and triple not in self.own else None
        entry = entry_factory()
        robbo = entry['robbo']
        dedup = (name, robbo['kind'], robbo['block_id'], robbo['label'], robbo['detail'], other_course)
        if dedup in self.seen:
            return
        self.seen.add(dedup)
        robbo['other_course'] = other_course
        robbo['published_only'] = published_only
        self.index.setdefault(name, []).append(entry)


def _entry(kind, url, display_location='', label='', field='', block_id='', path=None, detail=''):
    return {
        'display_location': display_location,
        'url': url,
        'robbo': {
            'kind': kind,
            'label': label,
            'detail': detail,
            'field': field,
            'block_id': block_id,
            'path': path or [],
        },
    }


def _path_node(block, position):
    return {
        'id': str(block.location),
        'name': getattr(block, 'display_name', '') or '',
        'type': block.category,
        'position': position,
    }


def _block_entry(path, field):
    """Usage entry of a block inside the course tree; ``path`` runs from the chapter down."""
    unit = path[2] if len(path) > 2 else None
    component = path[3] if len(path) > 3 else None
    subsection = path[1] if len(path) > 1 else None
    if unit and component:
        url = f"/container/{unit['id']}#{component['id']}"
        display_location = f"{subsection['name']} - {unit['name']} / {component['name']}"
    elif unit:
        url = f"/container/{unit['id']}"
        display_location = f"{subsection['name']} - {unit['name']}"
    else:
        url = ''
        display_location = ' - '.join(node['name'] for node in path)
    return _entry(
        'block', url, display_location=display_location, field=field,
        block_id=path[-1]['id'] if path else '', path=path,
    )


def _scan_course_block(builder, course):
    course_key = builder.course_key
    details_url = _course_url('settings/details', course_key)
    for field_name, kind in COURSE_IMAGE_FIELDS:
        builder.add_plain_name(
            getattr(course, field_name, ''),
            lambda kind=kind, field_name=field_name: _entry(
                kind, details_url, display_location=_('Schedule & Details'), field=field_name,
            ),
        )

    certificates = (getattr(course, 'certificates', None) or {}).get('certificates') or []
    for certificate in certificates:
        for signatory in certificate.get('signatories') or []:
            label = certificate.get('name', '')
            detail = signatory.get('name', '')
            builder.add_text(
                signatory.get('signature_image_path') or '',
                lambda label=label, detail=detail: _entry(
                    'certificate', _course_url('certificates', course_key),
                    display_location=_('Certificates'), label=label, field='certificates', detail=detail,
                ),
            )

    for field_name in ('pdf_textbooks', 'html_textbooks'):
        for textbook in getattr(course, field_name, None) or []:
            label = textbook.get('tab_title', '')
            builder.add_text(
                _value_text(textbook),
                lambda label=label, field_name=field_name: _entry(
                    'textbook', _course_url('textbooks', course_key),
                    display_location=_('Textbooks'), label=label, field=field_name,
                ),
            )

    for field_name, text in _iter_field_texts(course, skip=COURSE_SPECIAL_FIELDS):
        builder.add_text(
            text,
            lambda field_name=field_name: _entry(
                'course_settings', _course_url('settings/advanced', course_key),
                display_location=_('Advanced Settings'), label=field_name, field=field_name,
            ),
        )


def _detached_entry(block, course_key):
    category = block.category
    block_id = block.location.block_id
    if category == 'course_info':
        kind = COURSE_INFO_KINDS.get(block_id)
        if not kind:
            return None
        return lambda: _entry(
            kind, _course_url('course_info', course_key), display_location=_('Course Updates'),
            label=block_id, block_id=str(block.location),
        )
    kind = DETACHED_KINDS.get(category)
    if not kind:
        return None
    if kind == 'about':
        return lambda: _entry(
            'about', _course_url('settings/details', course_key), display_location=_('Schedule & Details'),
            label=block_id, block_id=str(block.location),
        )
    name = getattr(block, 'display_name', '') or block_id
    return lambda: _entry(
        'page', _course_url('tabs', course_key), display_location=_('Pages'),
        label=name, block_id=str(block.location),
    )


def _scan_branch(builder, published_only=False):
    store = modulestore()
    course_key = builder.course_key
    items = store.get_items(course_key)
    by_ident = {_ident(block.location): block for block in items}
    parent_of = {}
    for block in items:
        for position, child in enumerate(getattr(block, 'children', None) or []):
            parent_of[_ident(child)] = (block, position)

    path_cache = {}

    def path_to_root(block):
        ident = _ident(block.location)
        if ident in path_cache:
            return path_cache[ident]
        chain = []
        current, position = block, 0
        guard = 0
        while current is not None and current.category != 'course' and guard < 64:
            parent = parent_of.get(_ident(current.location))
            if parent is None:
                path_cache[ident] = None
                return None
            chain.append((current, parent[1]))
            current = parent[0]
            guard += 1
        path = [_path_node(node, pos) for node, pos in reversed(chain)] if current is not None else None
        path_cache[ident] = path
        return path

    for block in by_ident.values():
        if block.category == 'course':
            if not published_only:
                _scan_course_block(builder, block)
            continue
        texts = list(_iter_field_texts(block))
        if not texts:
            continue
        path = path_to_root(block)
        if path:
            for field_name, text in texts:
                builder.add_text(
                    text, lambda path=path, field_name=field_name: _block_entry(path, field_name),
                    published_only=published_only,
                )
            continue
        factory = _detached_entry(block, course_key)
        if factory is None:
            continue  # orphan
        for _field_name, text in texts:
            builder.add_text(text, factory, published_only=published_only)


def _versions(course_key):
    store = modulestore()
    versions = []
    for branch in (ModuleStoreEnum.Branch.draft_preferred, ModuleStoreEnum.Branch.published_only):
        with store.branch_setting(branch, course_key):
            course = store.get_course(course_key, depth=0)
        versions.append(str(getattr(course, 'course_version', None) or '') if course else '')
    return versions


def get_usage_index(course_key):
    """``{asset name: [usage entry, …]}`` for the whole course, cached per structure version."""
    store = modulestore()
    draft_version, published_version = _versions(course_key)
    cache_key = None
    if draft_version:
        digest = hashlib.md5(
            f'{course_key}|{draft_version}|{published_version}|{SCHEMA_V}'.encode()
        ).hexdigest()
        cache_key = f'robbo:asset-usage:{digest}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    builder = _IndexBuilder(course_key)
    with store.branch_setting(ModuleStoreEnum.Branch.draft_preferred, course_key):
        _scan_branch(builder)
    if published_version:
        with store.branch_setting(ModuleStoreEnum.Branch.published_only, course_key):
            _scan_branch(builder, published_only=True)

    for entries in builder.index.values():
        entries.sort(key=_sort_key)
    if cache_key:
        cache.set(cache_key, builder.index, CACHE_TTL)
    return builder.index


def _sort_key(entry):
    robbo = entry['robbo']
    kind = robbo['kind']
    order = KIND_ORDER.index(kind) if kind in KIND_ORDER else len(KIND_ORDER)
    positions = tuple(node['position'] for node in robbo['path'])
    return (order, positions, robbo['label'], robbo['published_only'])


def get_asset_usage_path(course_key, assets):
    """
    Drop-in for upstream ``_get_asset_usage_path``: ``{str(asset_key): [usage entry, …]}``.

    ``assets`` are dicts with ``asset_key`` (as returned by the contentstore listing).
    """
    try:
        index = get_usage_index(course_key)
    except Exception:  # pylint: disable=broad-except
        log.exception('Robbo asset usage: scan failed for %s', course_key)
        index = {}
    usage = {}
    for asset in assets:
        asset_key = asset['asset_key']
        name = asset_key.block_id
        entries = index.get(name)
        if entries is None:
            entries = index.get(unicodedata.normalize('NFC', name), [])
        usage[str(asset_key)] = [_public_entry(entry) for entry in entries]
    return usage


def _public_entry(entry):
    """A copy of the entry for the JSON response (the cached index stays untouched)."""
    robbo = dict(entry['robbo'])
    robbo['path'] = [dict(node) for node in robbo['path']]
    return {'display_location': entry['display_location'], 'url': entry['url'], 'robbo': robbo}
