"""
Robbo: the frame of notification emails — green «РОББО» header, white card, grey footer — shared by
«Сразу» letters (robbo_immediate.py) and digests (robbo_digest.py). Inline styles only: mail clients
drop <style> blocks.

Copyright (C) 2026 Robbo <https://robbo.ru>
SPDX-License-Identifier: AGPL-3.0-only
Part of the Robbo Open edX distribution. See NOTICE at repository root.
"""
from django.conf import settings
from django.utils.html import escape

GREEN = '#00af41'
GREEN_DARK = '#007e2f'
TEXT = '#1f2328'
MUTED = '#5f6670'
LINE = '#e8eaed'
FONT = 'Helvetica,Arial,sans-serif'

TEXTS = {
    'ru': {
        'settings': 'Настроить уведомления',
        'unsubscribe': 'Отписаться от писем с уведомлениями',
        'open': 'Открыть',
        'all': 'Все уведомления',
    },
    'en': {
        'settings': 'Notification settings',
        'unsubscribe': 'Unsubscribe from notification emails',
        'open': 'Open',
        'all': 'All notifications',
    },
}


def account_url(path=''):
    # Studio has no ACCOUNT_MICROFRONTEND_URL (its letters: co-author published, import / export):
    # our MFEs live on the LMS host, under /account.
    base = getattr(settings, 'ACCOUNT_MICROFRONTEND_URL', None) or f"{settings.LMS_ROOT_URL.rstrip('/')}/account/"
    return f"{base.rstrip('/')}/{path}"


def settings_url():
    return account_url('#notifications')


def feed_url():
    return account_url('notifications')


def button(url, label):
    return (
        f'<a href="{escape(url)}" style="display:inline-block;padding:10px 20px;border-radius:999px;'
        f'background:{GREEN};color:#ffffff;font-weight:700;font-size:15px;text-decoration:none">{escape(label)}</a>'
    )


def frame(lang, body_html, note, title='', subtitle='', unsubscribe_url=''):
    """The whole letter. body_html is trusted HTML built by the callers (values already escaped)."""
    texts = TEXTS[lang]
    heading = ''
    if title:
        heading = (
            f'<div style="padding:24px 24px 0">'
            f'<h1 style="margin:0;color:{TEXT};font-size:22px;line-height:1.3;font-weight:800">{escape(title)}</h1>'
            + (f'<p style="margin:4px 0 0;color:{MUTED};font-size:14px">{escape(subtitle)}</p>' if subtitle else '')
            + '</div>'
        )
    links = f'<a href="{escape(settings_url())}" style="color:{GREEN_DARK}">{escape(texts["settings"])}</a>'
    if unsubscribe_url:
        links += (f' &nbsp;·&nbsp; <a href="{escape(unsubscribe_url)}" style="color:{MUTED}">'
                  f'{escape(texts["unsubscribe"])}</a>')
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"></head><body style="margin:0">'
        f'<div style="margin:0;padding:24px 12px;background:#f4f5f6;font-family:{FONT}">'
        '<div style="max-width:600px;margin:0 auto;background:#ffffff;border-radius:16px;overflow:hidden">'
        f'<div style="padding:18px 24px;background:{GREEN};color:#ffffff;font-size:20px;font-weight:800">РОББО</div>'
        f'{heading}<div style="padding:20px 24px 24px">{body_html}</div>'
        f'<div style="padding:16px 24px;border-top:1px solid {LINE};color:{MUTED};font-size:12px;line-height:1.6">'
        f'{escape(note)}<br>{links}</div>'
        '</div></div></body></html>'
    )
