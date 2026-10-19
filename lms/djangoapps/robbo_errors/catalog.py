# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (human-readable errors). See NOTICE at repository root.
"""
The catalog of error codes (``catalog.yaml``): what each code means to the user and to support.

Texts are in Russian and English side by side, like «Что нового»; the user's active language picks
one (``robbo_changelog.labels.current_lang``), so no gettext catalogs are involved.
"""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from lms.djangoapps.robbo_changelog.labels import current_lang

CATALOG_PATH = Path(__file__).with_name('catalog.yaml')
LANGUAGES = ('ru', 'en')
JOURNAL_MODES = ('case', 'count')

# Codes the server falls back to when it knows only the HTTP status.
STATUS_CODES = {
    400: 'BAD-INPUT',
    401: 'SESSION-EXPIRED',
    403: 'ACCESS-DENIED',
    404: 'NOT-FOUND',
    413: 'UPLOAD-SIZE',
    429: 'TOO-MANY',
    502: 'SRV-RESTART',
    503: 'SRV-RESTART',
    504: 'SRV-RESTART',
}
FALLBACK_CODE = 'SRV-ERROR'


@dataclass(frozen=True)
class ErrorKind:
    """One code of the catalog."""

    code: str
    status: int | None
    journal: str
    caddy: bool
    title: dict
    message: dict
    message_fallback: dict | None
    support: str


@dataclass(frozen=True)
class ErrorText:
    """What the user sees: the title and the message in one language."""

    title: str
    message: str


def _check_texts(where, texts):
    if not isinstance(texts, dict) or any(not texts.get(lang) for lang in LANGUAGES):
        raise ValueError(f'{CATALOG_PATH.name}: {where} needs non-empty texts in {", ".join(LANGUAGES)}')
    return texts


@lru_cache(maxsize=None)
def load():
    """``(codes, ui)`` of the catalog file, validated once per process."""
    data = yaml.safe_load(CATALOG_PATH.read_text(encoding='utf-8'))
    codes = {}
    for code, entry in data['codes'].items():
        journal = entry.get('journal', 'case')
        if journal not in JOURNAL_MODES:
            raise ValueError(f'{CATALOG_PATH.name}: {code}.journal must be one of {JOURNAL_MODES}')
        fallback = entry.get('message_fallback')
        codes[code] = ErrorKind(
            code=code,
            status=entry.get('status'),
            journal=journal,
            caddy=bool(entry.get('caddy')),
            title=_check_texts(f'{code}.title', entry.get('title')),
            message=_check_texts(f'{code}.message', entry.get('message')),
            message_fallback=_check_texts(f'{code}.message_fallback', fallback) if fallback else None,
            support=entry.get('support', ''),
        )
    ui = data['ui']
    for key, value in ui.items():
        if key != 'support_url':
            _check_texts(f'ui.{key}', value)
    return codes, ui


def codes():
    return load()[0]


def get(code):
    """The ``ErrorKind`` of ``code``, or ``None`` for a code the catalog does not know."""
    return codes().get(code)


def code_for_status(status):
    """The general code for an HTTP status, when nothing more exact is known."""
    return STATUS_CODES.get(status, FALLBACK_CODE if status >= 500 else 'BAD-INPUT')


def ui_text(key, lang=None):
    return load()[1][key][lang or current_lang()]


def support_url():
    return load()[1]['support_url']


def split_link(text):
    """``'… или [напишите в поддержку]'`` → ``('… или ', 'напишите в поддержку', '')``."""
    before, _, rest = text.partition('[')
    link, _, after = rest.partition(']')
    return (before, link, after) if link else (text, '', '')


def describe(code, lang=None, **params):
    """
    The user's text for ``code``; ``params`` fill ``{placeholders}`` of the message (e.g. ``limit``).

    An unknown code gets the text of ``SRV-ERROR``: the user still sees something meaningful while
    the code itself (shown next to the text) tells support what happened.
    """
    lang = lang or current_lang()
    kind = get(code) or get(FALLBACK_CODE)
    try:
        message = kind.message[lang].format(**params)
    except (KeyError, IndexError):
        message = (kind.message_fallback or kind.message)[lang]
    return ErrorText(title=kind.title[lang], message=message)
