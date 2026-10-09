# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (site changelog). See NOTICE at repository root.
"""
Releases of «Что нового» as the current viewer sees them, and what they have not read yet.

Filtering happens here, on the server: entries of other sites and of audiences the viewer
does not belong to never reach the page or the header panel.
"""

import json
import logging
import re
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.templatetags.static import static

from openedx.core.djangoapps.theming.helpers import get_current_theme
from openedx.core.djangoapps.user_api.models import UserPreference
from openedx.core.lib.robbo_stack import ROBBO_STACK_PROFILE

from . import labels, schema
from .access import is_platform_staff, viewer_audiences

log = logging.getLogger(__name__)

RELEASES_DIR = Path(__file__).resolve().parent / 'releases'
PARAGRAPH_SPLIT_RE = re.compile(r'\n\s*\n')

# Last release the user has seen and its entry ids (entries can be added to a release later).
SEEN_PREFERENCE = 'robbo-whats-new-seen'
# Header panel: releases with unread entries, at least the latest few. Only the latest
# PANEL_MAX_RELEASES count as unread at all, so the dot never promises more than the panel shows.
PANEL_MIN_RELEASES = 3
PANEL_MAX_RELEASES = 10


@lru_cache(maxsize=1)
def releases():
    """Valid releases, newest first; read once per process (files ship with the image)."""
    found, errors = schema.load_releases(RELEASES_DIR)
    for error in errors:
        log.warning('robbo_changelog: %s', error)
    return found


def load_errors():
    """Problems of the release files (for preflight; the page just skips broken files)."""
    return schema.load_releases(RELEASES_DIR)[1]


def visible_releases(user):
    """``[(release, entries)]`` of this site that ``user`` may see, newest first; empty for guests."""
    audiences = viewer_audiences(user)
    visible = []
    for release in releases():
        entries = [entry for entry in release['entries']
                   if ROBBO_STACK_PROFILE in entry['sites'] and entry['audience'] in audiences]
        if entries:
            visible.append((release, entries))
    return visible


def unread_ids(user, visible):
    """Ids of entries in the latest visible releases newer than what ``user`` last saw (all, if never)."""
    try:
        seen = json.loads(UserPreference.get_value(user, SEEN_PREFERENCE) or 'null')
    except ValueError:
        seen = None
    marker = schema.stem_key(seen.get('release')) if isinstance(seen, dict) else None
    seen_ids = set(seen.get('ids') or []) if marker else set()
    unread = set()
    for release, entries in visible[:PANEL_MAX_RELEASES]:
        key = schema.release_key(release)
        if marker is None or key > marker:
            unread.update(entry['id'] for entry in entries)
        elif key == marker:
            unread.update(entry['id'] for entry in entries if entry['id'] not in seen_ids)
    return unread


def mark_read(user, visible):
    """Remember the newest visible release and its entries as seen by ``user``."""
    if not visible:
        return
    newest, entries = visible[0]
    value = json.dumps({'release': schema.release_stem(newest), 'ids': sorted(entry['id'] for entry in entries)})
    UserPreference.objects.update_or_create(user=user, key=SEEN_PREFERENCE, defaults={'value': value})


def resolve_link(target):
    """``studio:/home`` → absolute URL of the current site, or ``None`` if not configured."""
    prefix, _, path = target.partition(':')
    base = {
        'lms': settings.LMS_ROOT_URL,
        'studio': getattr(settings, 'CMS_ROOT_URL', ''),
        'account': settings.ACCOUNT_MICROFRONTEND_URL,
        'learning': settings.LEARNING_MICROFRONTEND_URL,
        'dashboard': settings.LEARNER_HOME_MICROFRONTEND_URL,
    }.get(prefix)
    if not base:
        return None
    return base.rstrip('/') + (path or '/')


def image_url(image):
    """
    Absolute URL of a theme screenshot on the LMS (the header panel is shown on other hosts too).

    Studio serves the same API to its Mako pages, but its ``static()`` points at Studio's files:
    there the URL leads to the theme folder the LMS collects (it keeps unhashed copies too).
    """
    if settings.ROOT_URLCONF == 'cms.urls':
        theme = get_current_theme()
        folder = f'{theme.theme_dir_name}/' if theme else ''
        return f"{settings.LMS_ROOT_URL.rstrip('/')}/static/{folder}images/{image}"
    url = static(f'images/{image}')
    return url if url.startswith(('http://', 'https://')) else settings.LMS_ROOT_URL.rstrip('/') + url


def section_code(entry):
    """``platform`` for entries touching two or more sections, else their only section."""
    sections = entry['sections']
    return 'platform' if len(sections) > 1 else sections[0]


def _sort_key(indexed):
    index, entry = indexed
    return schema.IMPORTANCE.index(entry['importance']), schema.KINDS.index(entry['kind']), index


def _entry_view(entry, lang, unread):
    view = {
        'id': entry['id'],
        'importance': entry['importance'],
        'kind': entry['kind'],
        'kind_label': labels.pick(labels.KINDS[entry['kind']], lang),
        'section_label': labels.pick(labels.SECTIONS[section_code(entry)], lang),
        'audience': entry['audience'],
        'audience_label': None,
        'title': labels.pick(entry['title'], lang),
        'paragraphs': [part.strip() for part in PARAGRAPH_SPLIT_RE.split(labels.pick(entry['text'], lang))
                       if part.strip()],
        'action': labels.pick(entry['action'], lang) if 'action' in entry else None,
        'link_url': None,
        'link_label': None,
        'image': entry.get('image'),
        'image_url': image_url(entry['image']) if 'image' in entry else None,
        'unread': entry['id'] in unread,
    }
    if entry['audience'] != 'all':
        view['audience_label'] = labels.pick(labels.AUDIENCES[entry['audience']], lang)
    if 'link' in entry:
        view['link_url'] = resolve_link(entry['link']['to'])
        view['link_label'] = labels.pick(entry['link']['label'], lang) if view['link_url'] else None
    return view


def _days(visible):
    """Releases of one day are shown under one date: ``[(releases, entries)]``, newest first."""
    days = []
    for release, entries in visible:
        if days and days[-1][0][0]['date'] == release['date']:
            days[-1][0].append(release)
            days[-1][1].extend(entries)
        else:
            days.append(([release], list(entries)))
    return days


def _day_view(day_releases, entries, lang, unread, show_version):
    """One day for the page or the panel: groups by importance, entries sorted by kind."""
    date = day_releases[0]['date']
    chosen = sorted(enumerate(entries), key=_sort_key)
    groups = []
    for importance in schema.IMPORTANCE:
        group = [_entry_view(entry, lang, unread) for _, entry in chosen if entry['importance'] == importance]
        if group:
            groups.append({
                'importance': importance,
                'heading': labels.pick(labels.IMPORTANCE[importance], lang),
                'entries': group,
            })
    return {
        'anchor': f'release-{date.isoformat()}',
        'date_iso': date.isoformat(),
        'date_label': labels.format_date(date, lang),
        'version': ', '.join(release['version'] for release in day_releases) if show_version else None,
        'groups': groups,
    }


def _matches(entry, section, audience):
    if section and section not in entry['sections'] and section != section_code(entry):
        return False
    return not audience or entry['audience'] == audience


def texts(lang, unread_count=0):
    """Interface texts of the page and the header panel in one language."""
    result = {key: labels.pick(value, lang) for key, value in labels.PAGE.items()}
    result['button_label'] = (labels.pick(labels.PAGE['button_unread'], lang).format(count=unread_count)
                              if unread_count else result['title'])
    result['summary'] = labels.unread_summary(unread_count, lang)
    return result


def status(user, lang):
    """Header button state: how many visible entries ``user`` has not read."""
    unread = unread_ids(user, visible_releases(user))
    return {'unread': len(unread), 'texts': texts(lang, len(unread))}


def panel(user, lang):
    """Header panel: releases with unread entries plus the latest few; unread entries are flagged."""
    visible = visible_releases(user)
    unread = unread_ids(user, visible)
    with_unread = [index for index, (_, entries) in enumerate(visible)
                   if any(entry['id'] in unread for entry in entries)]
    count = min(max(PANEL_MIN_RELEASES, with_unread[-1] + 1 if with_unread else 0), PANEL_MAX_RELEASES)
    show_version = is_platform_staff(viewer_audiences(user))
    return {
        'unread': len(unread),
        'texts': texts(lang, len(unread)),
        'releases': [_day_view(day_releases, entries, lang, unread, show_version)
                     for day_releases, entries in _days(visible[:count])],
        'more': len(visible) > count,
        'page_url': settings.LMS_ROOT_URL.rstrip('/') + '/whats-new',
    }


def build_page(user, section=None, audience=None, lang=None):
    """
    Template context of ``/whats-new`` for ``user``, optionally filtered by section and audience.

    Unread entries are flagged; the caller marks them read after rendering.
    """
    lang = lang or labels.current_lang()
    audiences = viewer_audiences(user)
    staff_audiences = [code for code in schema.STAFF_AUDIENCES if code in audiences]
    visible = visible_releases(user)
    unread = unread_ids(user, visible)

    present_sections = {code for _, entries in visible for entry in entries
                        for code in (*entry['sections'], section_code(entry))}
    present_audiences = {entry['audience'] for _, entries in visible for entry in entries}
    section = section if section in present_sections else None
    audience = audience if staff_audiences and audience in present_audiences else None

    page_releases = []
    for day_releases, entries in _days(visible):
        chosen = [entry for entry in entries if _matches(entry, section, audience)]
        if chosen:
            page_releases.append(_day_view(day_releases, chosen, lang, unread, is_platform_staff(audiences)))

    # Filters are two compact dropdowns (GET form): value '' — no filter.
    section_options = [{
        'value': '',
        'label': labels.pick(labels.PAGE['any_section'], lang),
        'selected': section is None,
    }] + [{
        'value': code,
        'label': labels.pick(labels.SECTIONS[code], lang),
        'selected': section == code,
    } for code in schema.SECTIONS if code in present_sections]

    audience_options = []
    if staff_audiences and len(present_audiences) > 1:
        audience_options = [{
            'value': '',
            'label': labels.pick(labels.PAGE['any_audience'], lang),
            'selected': audience is None,
        }] + [{
            'value': code,
            'label': labels.pick(labels.PAGE['audience_all'] if code == 'all' else labels.AUDIENCES[code], lang),
            'selected': audience == code,
        } for code in schema.AUDIENCES if code in present_audiences]

    return {
        'texts': texts(lang),
        'lang': lang,
        'is_staff_viewer': bool(staff_audiences),
        'releases': page_releases,
        'has_any': bool(visible),
        'filtered': bool(section or audience),
        'section_options': section_options if len(section_options) > 2 else [],
        'audience_options': audience_options,
        'visible': visible,
    }
