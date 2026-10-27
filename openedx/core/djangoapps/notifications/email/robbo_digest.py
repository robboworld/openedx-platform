"""
Robbo: daily / weekly notification digest in the Robbo design and the recipient's language.

The stock digest (ACE template email_digest) is English and looks unlike our «Сразу» letters. Here
send_digest_email_to_user (tasks.py) hands over the notifications it picked and the digest goes out
in the shared frame (robbo_layout.py): one section per app, up to five notifications each with type,
text (robbo_texts.py), course and time, «Все уведомления», settings and one-click unsubscribe (also
in the List-Unsubscribe headers, as the stock digest does).

Copyright (C) 2026 Robbo <https://robbo.ru>
SPDX-License-Identifier: AGPL-3.0-only
Part of the Robbo Open edX distribution. See NOTICE at repository root.
"""
import pytz
from django.core.mail import EmailMultiAlternatives
from django.utils.html import escape

from openedx.core.djangoapps.notifications.email.robbo_layout import (
    GREEN_DARK, LINE, MUTED, TEXT, account_url, button, feed_url, frame,
)
from openedx.core.djangoapps.notifications.robbo_texts import (
    notification_from_email, notification_html, notification_text, type_label,
)
from openedx.core.djangoapps.user_api.models import UserPreference

PER_APP = 5
APP_ORDER = ['updates', 'learning', 'grading', 'learner_progress', 'discussion', 'authoring']
MONTHS_RU = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября',
             'ноября', 'декабря']
MONTHS_EN = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October',
             'November', 'December']

TEXTS = {
    'ru': {
        'apps': {'updates': 'Обновления курса', 'grading': 'Задания', 'learner_progress': 'Прогресс учеников',
                 'discussion': 'Обсуждения', 'learning': 'Учёба', 'authoring': 'Студия'},
        'title': {'Daily': 'Уведомления за день', 'Weekly': 'Уведомления за неделю'},
        'subject': {'Daily': 'Уведомления РОББО за {date}', 'Weekly': 'Уведомления РОББО за неделю: {date}'},
        'note': {'Daily': 'Вы получили эту сводку, потому что в настройках уведомлений выбрали письма «раз в день».',
                 'Weekly': 'Вы получили эту сводку, потому что в настройках уведомлений выбрали письма «раз в неделю».'},
        'more': 'Ещё {count} — во всех уведомлениях',
        'open': 'Открыть',
        'all': 'Все уведомления',
    },
    'en': {
        'apps': {'updates': 'Course updates', 'grading': 'Assignments', 'learner_progress': 'Learner progress',
                 'discussion': 'Discussions', 'learning': 'Learning', 'authoring': 'Studio'},
        'title': {'Daily': 'Notifications of the day', 'Weekly': 'Notifications of the week'},
        'subject': {'Daily': 'ROBBO notifications for {date}', 'Weekly': 'ROBBO notifications of the week: {date}'},
        'note': {'Daily': 'You get this digest because your notification settings send letters once a day.',
                 'Weekly': 'You get this digest because your notification settings send letters once a week.'},
        'more': '{count} more in all notifications',
        'open': 'Open',
        'all': 'All notifications',
    },
}


def ru_count(n):
    """«1 новое уведомление», «3 новых уведомления», «5 новых уведомлений»."""
    if n % 10 == 1 and n % 100 != 11:
        return f'{n} новое уведомление'
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return f'{n} новых уведомления'
    return f'{n} новых уведомлений'


def _zone(user, lang):
    name = UserPreference.get_value(user, 'time_zone') or ('Europe/Moscow' if lang == 'ru' else 'UTC')
    try:
        return pytz.timezone(name)
    except pytz.UnknownTimeZoneError:
        return pytz.UTC


def _day(moment, lang, with_year=True):
    months = MONTHS_RU if lang == 'ru' else MONTHS_EN
    if lang == 'ru':
        text = f'{moment.day} {months[moment.month - 1]}'
    else:
        text = f'{months[moment.month - 1]} {moment.day}'
    return f'{text} {moment.year}' if with_year else text


def _period(start, end, cadence, lang):
    if cadence == 'Weekly' and start.date() != end.date():
        return f'{_day(start, lang, with_year=False)} – {_day(end, lang)}'
    return _day(end, lang)


def _app_section(app, items, more, texts, lang, zone):
    rows = []
    for notification in items:
        course = notification.content_context.get('course_name', '') or getattr(notification, 'course_name', '')
        when = notification.created.astimezone(zone)
        meta = ' · '.join(filter(None, [course, f'{_day(when, lang, with_year=False)}, {when:%H:%M}']))
        link = (f' &nbsp;<a href="{escape(notification.content_url)}" style="color:{GREEN_DARK};font-weight:700;'
                f'text-decoration:none">{escape(texts["open"])} →</a>') if notification.content_url else ''
        rows.append(
            f'<div style="padding:12px 0;border-top:1px solid {LINE}">'
            f'<div style="color:{GREEN_DARK};font-size:12px;font-weight:700">'
            f'{escape(type_label(notification.notification_type, lang))}</div>'
            f'<div style="margin:2px 0 4px;color:{TEXT};font-size:15px;line-height:1.45">'
            f'{notification_html(notification.notification_type, notification.content_context, lang)}</div>'
            f'<div style="color:{MUTED};font-size:12px">{escape(meta)}{link}</div></div>'
        )
    if more:
        rows.append(f'<div style="padding:8px 0 0"><a href="{escape(feed_url())}" style="color:{GREEN_DARK};'
                    f'font-size:13px">{escape(texts["more"].format(count=more))}</a></div>')
    return (f'<h2 style="margin:20px 0 4px;color:{TEXT};font-size:16px;font-weight:800">'
            f'{escape(texts["apps"].get(app, app))} · {len(items) + more}</h2>' + ''.join(rows))


def send_robbo_digest(user, cadence_type, notifications, start_date, end_date, lang, unsubscribe_url):
    """Builds and sends the digest. notifications: the ones send_digest_email_to_user picked."""
    texts = TEXTS[lang]
    zone = _zone(user, lang)
    start, end = start_date.astimezone(zone), end_date.astimezone(zone)
    by_app = {}
    for notification in sorted(notifications, key=lambda n: n.created, reverse=True):
        by_app.setdefault(notification.app_name, []).append(notification)
    apps = [app for app in APP_ORDER if app in by_app] + [app for app in by_app if app not in APP_ORDER]
    total = len(notifications)

    count = ru_count(total) if lang == 'ru' else f'{total} new notification{"s" if total != 1 else ""}'
    chips = ' '.join(
        f'<span style="display:inline-block;margin:0 6px 6px 0;padding:3px 10px;border-radius:999px;'
        f'background:#e3f6ea;color:{GREEN_DARK};font-size:12px;font-weight:700">'
        f'{escape(texts["apps"].get(app, app))} · {len(by_app[app])}</span>'
        for app in apps
    )
    sections = ''.join(
        _app_section(app, by_app[app][:PER_APP], max(0, len(by_app[app]) - PER_APP), texts, lang, zone)
        for app in apps
    )
    inner = (
        f'<p style="margin:0 0 10px;color:{TEXT};font-size:15px;font-weight:700">{escape(count)}</p>'
        f'<div>{chips}</div>{sections}'
        f'<div style="margin-top:24px">{button(feed_url(), texts["all"])}</div>'
    )
    period = _period(start, end, cadence_type, lang)
    html = frame(lang, inner, texts['note'].get(cadence_type, ''), title=texts['title'].get(cadence_type, ''),
                 subtitle=period, unsubscribe_url=unsubscribe_url)

    lines = [texts['title'].get(cadence_type, ''), period, count, '']
    for app in apps:
        lines.append(texts['apps'].get(app, app))
        lines += [f'- {notification_text(n.notification_type, n.content_context, lang)}' for n in by_app[app][:PER_APP]]
        lines.append('')
    lines += [f'{texts["all"]}: {feed_url()}', account_url('#notifications')]
    subject = texts['subject'].get(cadence_type, texts['subject']['Daily']).format(
        date=_period(start, end, cadence_type, lang) if cadence_type == 'Weekly' else _day(end, lang, with_year=False)
    )
    message = EmailMultiAlternatives(subject, '\n'.join(lines), notification_from_email(), [user.email])
    message.attach_alternative(html, 'text/html')
    if unsubscribe_url:
        message.extra_headers['List-Unsubscribe'] = f'<{unsubscribe_url}>'
        message.extra_headers['List-Unsubscribe-Post'] = 'List-Unsubscribe=One-Click'
    message.send()
