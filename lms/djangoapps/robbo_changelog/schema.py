# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (site changelog). See NOTICE at repository root.
"""
Release file format of «Что нового» and its validation.

Pure Python (only PyYAML): the LMS loads releases through it, and the host-side preflight
(``scripts/lib/preflight/static_checks.py`` in the meta-repo) imports this file by path to
check the same rules before a commit or an image build.
"""

import datetime
import re
from pathlib import Path

SITES = ('online', 'skill', 'courses')
LANGS = ('ru', 'en')

# Who an entry is for. ``all`` — learners and staff; the rest — staff only, shown with a label.
AUDIENCES = ('all', 'authors', 'teachers', 'platform_staff', 'platform_admins')
STAFF_AUDIENCES = AUDIENCES[1:]

# Order on the page: new features and global interface changes first, small fixes last.
IMPORTANCE = ('major', 'notable', 'minor')
# ``important`` — something to pay attention to (changed behaviour, needs action); sorts first.
KINDS = ('important', 'new', 'improved', 'fixed')

# ``platform`` — the whole platform; an entry listing two or more sections is shown the same way.
SECTIONS = (
    'platform', 'home', 'dashboard', 'courseware', 'assignments', 'certificates', 'payments',
    'account', 'auth', 'discussions', 'emails', 'personal_account', 'studio', 'instructor',
)
STAFF_SECTIONS = ('studio', 'instructor')

# «Где посмотреть»: internal links only, the prefix is resolved from LMS settings of the site.
LINK_PREFIXES = ('lms', 'studio', 'account', 'learning', 'dashboard')

ENTRY_KEYS = ('id', 'sites', 'audience', 'importance', 'kind', 'sections',
              'title', 'text', 'action', 'link', 'image')
REQUIRED_KEYS = ENTRY_KEYS[:8]
TEXT_LIMITS = {'title': 140, 'text': 1500, 'action': 500, 'label': 60}

FILENAME_RE = re.compile(r'^(\d{4}-\d{2}-\d{2})_([0-9A-Za-z][0-9A-Za-z.+-]{0,39})\.yaml$')
VERSION_RE = re.compile(r'^[0-9A-Za-z][0-9A-Za-z.+-]{0,39}$')
ID_RE = re.compile(r'^[a-z0-9][a-z0-9-]{2,79}$')
LINK_RE = re.compile(r'^(%s):(/[A-Za-z0-9._~/-]*)?$' % '|'.join(LINK_PREFIXES))
IMAGE_RE = re.compile(r'^whats-new/[a-z0-9][a-z0-9_-]*\.(?:png|jpe?g|webp|svg)$')
CYRILLIC_RE = re.compile(r'[А-Яа-яЁё]')

# Safety net for texts that could help to harm users, staff or the infrastructure. The real
# filter is the author (see .cursor/rules/site-changelog.mdc): these only catch obvious leaks.
LEAK_PATTERNS = (
    (re.compile(r'\b[A-Za-z0-9_-]+\.(?:py|js|jsx|ts|tsx|html|mako|scss|css|ya?ml|json|sh|po|mo|cfg|ini|env)\b',
                re.I),
     'имя файла'),
    (re.compile(r'(?:^|[\s(«"])/(?:[A-Za-z0-9_.-]+/)+'), 'путь'),
    (re.compile(r'/api/|/admin\b|\bdjango[\s-]?admin\b|\bmanage\.py\b', re.I), 'служебный адрес'),
    (re.compile(r'\b(?:docker|tutor|kubernetes|k8s|nginx|caddy|uwsgi|gunicorn|celery|redis|mysql|'
                r'mongo(?:db)?|elasticsearch|meilisearch|ssh|sudo|cron(?:tab)?|git|submodules?|'
                r'cherry-pick|webpack|buildkit|registry)\b', re.I),
     'инфраструктура'),
    (re.compile(r'\b(?:secrets?|tokens?|api[\s_-]?keys?|webhooks?|hmac|jwt|csrf|xss|sql[\s-]?injection|'
                r'exploits?|vulnerabilit(?:y|ies)|cve-\d+)\b', re.I),
     'безопасность'),
    (re.compile(r'уязвим|токен|секретн\w*\s+ключ|бэкап|резервн\w*\s+коп', re.I), 'безопасность'),
    (re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'), 'IP-адрес'),
    (re.compile(r'\b(?:localhost|[a-z][\w.-]*:\d{2,5})\b', re.I), 'адрес или порт'),
    (re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+'), 'адрес почты'),
    (re.compile(r'\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:ru|world|com|io|net|org|dev|local|test)\b', re.I),
     'домен (ссылка — только через link.to)'),
)


def leaks(text):
    """Names of the leak patterns ``text`` matches."""
    return [name for pattern, name in LEAK_PATTERNS if pattern.search(text)]


def _check_texts(value, field, errors, limit):
    if not isinstance(value, dict) or set(value) != set(LANGS):
        errors.append(f'{field}: нужны ровно ключи ru и en')
        return
    for lang in LANGS:
        text = value[lang]
        if not isinstance(text, str) or not text.strip():
            errors.append(f'{field}.{lang}: пустой текст')
            continue
        if len(text) > limit:
            errors.append(f'{field}.{lang}: длиннее {limit} символов')
        if lang == 'ru' and not CYRILLIC_RE.search(text):
            errors.append(f'{field}.ru: нет русского текста')
        if lang == 'en' and CYRILLIC_RE.search(text):
            errors.append(f'{field}.en: кириллица в английском тексте')
        for name in leaks(text):
            errors.append(f'{field}.{lang}: похоже на утечку ({name})')


def _check_list(value, field, allowed, errors):
    if not isinstance(value, list) or not value:
        errors.append(f'{field}: нужен непустой список')
        return []
    unknown = [item for item in value if item not in allowed]
    if unknown:
        errors.append(f'{field}: неизвестные значения {unknown}')
    if len(set(map(str, value))) != len(value):
        errors.append(f'{field}: повторы')
    return value


def validate_entry(entry, image_root=None):
    """Problems of one entry, as human-readable strings (empty list — valid)."""
    if not isinstance(entry, dict):
        return ['запись должна быть словарём']
    errors = []
    unknown = sorted(set(entry) - set(ENTRY_KEYS))
    if unknown:
        errors.append(f'лишние поля {unknown}')
    missing = [key for key in REQUIRED_KEYS if key not in entry]
    if missing:
        errors.append(f'нет полей {missing}')
        return errors
    if not isinstance(entry['id'], str) or not ID_RE.match(entry['id']):
        errors.append('id: латиница в нижнем регистре, цифры и дефис, 3–80 символов')
    _check_list(entry['sites'], 'sites', SITES, errors)
    sections = _check_list(entry['sections'], 'sections', SECTIONS, errors)
    if 'platform' in sections and len(sections) > 1:
        errors.append('sections: platform указывается один')
    for key, allowed in (('audience', AUDIENCES), ('importance', IMPORTANCE), ('kind', KINDS)):
        if entry[key] not in allowed:
            errors.append(f'{key}: одно из {list(allowed)}')
    if entry['audience'] == 'all' and sections and set(sections) <= set(STAFF_SECTIONS):
        errors.append('audience all, но разделы только для персонала')
    for key in ('title', 'text', 'action'):
        if key in entry:
            _check_texts(entry[key], key, errors, TEXT_LIMITS[key])
    if 'link' in entry:
        link = entry['link']
        if not isinstance(link, dict) or set(link) != {'to', 'label'}:
            errors.append('link: нужны поля to и label')
        else:
            if not isinstance(link['to'], str) or not LINK_RE.match(link['to']) or '..' in link['to']:
                errors.append(f'link.to: <{"|".join(LINK_PREFIXES)}>:/путь, без домена и параметров')
            _check_texts(link['label'], 'link.label', errors, TEXT_LIMITS['label'])
    if 'image' in entry:
        image = entry['image']
        if not isinstance(image, str) or not IMAGE_RE.match(image):
            errors.append('image: whats-new/<имя>.png|jpg|webp|svg')
        elif image_root is not None and not (Path(image_root) / image).is_file():
            errors.append(f'image: нет файла {image}')
    return errors


def _parse_date(value):
    if isinstance(value, datetime.date) and not isinstance(value, datetime.datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.date.fromisoformat(value)
        except ValueError:
            pass
    return None


def validate_release(data, filename, image_root=None):
    """
    Problems of one release file and the release itself, normalized.

    Returns ``(errors, release)``; ``release`` is ``None`` when the file is invalid.
    """
    match = FILENAME_RE.match(filename)
    if not match:
        return [f'{filename}: имя файла — ГГГГ-ММ-ДД_<версия>.yaml'], None
    if not isinstance(data, dict):
        return [f'{filename}: файл должен быть словарём version/date/entries'], None
    errors = []
    unknown = sorted(set(data) - {'version', 'date', 'entries'})
    if unknown:
        errors.append(f'{filename}: лишние поля {unknown}')
    version = data.get('version')
    if not isinstance(version, str) or not VERSION_RE.match(version):
        errors.append(f'{filename}: version — строка в кавычках, например "1.3.6"')
    elif version != match.group(2):
        errors.append(f'{filename}: version не совпадает с именем файла')
    date = _parse_date(data.get('date'))
    if date is None:
        errors.append(f'{filename}: date — ГГГГ-ММ-ДД')
    elif date.isoformat() != match.group(1):
        errors.append(f'{filename}: date не совпадает с именем файла')
    entries = data.get('entries')
    if not isinstance(entries, list) or not entries:
        errors.append(f'{filename}: entries — непустой список')
        entries = []
    for index, entry in enumerate(entries):
        label = entry.get('id') if isinstance(entry, dict) and entry.get('id') else f'#{index + 1}'
        errors += [f'{filename} [{label}]: {problem}' for problem in validate_entry(entry, image_root)]
    if errors:
        return errors, None
    return [], {'version': version, 'date': date, 'entries': entries, 'filename': filename}


def load_releases(directory, image_root=None):
    """
    Read and validate every ``*.yaml`` release in ``directory``.

    Returns ``(releases, errors)``: valid releases, newest first; invalid files are skipped and
    listed in ``errors``, as are ids repeated across files.
    """
    import yaml  # pylint: disable=import-outside-toplevel

    releases, errors, seen = [], [], {}
    for path in sorted(Path(directory).glob('*.yaml')):
        try:
            data = yaml.safe_load(path.read_text(encoding='utf-8'))
        except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
            errors.append(f'{path.name}: {exc}')
            continue
        problems, release = validate_release(data, path.name, image_root)
        if problems:
            errors += problems
            continue
        for entry in release['entries']:
            if entry['id'] in seen:
                errors.append(f'{path.name} [{entry["id"]}]: id уже есть в {seen[entry["id"]]}')
            seen.setdefault(entry['id'], path.name)
        releases.append(release)
    releases.sort(key=release_key, reverse=True)
    return releases, errors


def _version_key(version):
    return tuple(int(part) if part.isdigit() else -1 for part in re.split(r'[.+-]', version))


def release_key(release):
    """Sort key of a loaded release: newer releases compare greater."""
    return release['date'], _version_key(release['version'])


def release_stem(release):
    """``2026-10-07_1.3.5`` — the file name without ``.yaml``, used as a stable release id."""
    return release['filename'][:-len('.yaml')]


def stem_key(stem):
    """Sort key of a release id from ``release_stem``; ``None`` if it is not one."""
    match = FILENAME_RE.match(f'{stem}.yaml') if isinstance(stem, str) else None
    if not match:
        return None
    date = _parse_date(match.group(1))
    return (date, _version_key(match.group(2))) if date else None
