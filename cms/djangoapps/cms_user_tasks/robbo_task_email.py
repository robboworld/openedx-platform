"""
Robbo: the «task finished» letter of Studio in the Robbo frame and the recipient's language.

The stock letter (tasks.py) is plain text with an English status («Succeeded»), the course key in
lower case and a link to a JSON API. Library export / import and the course link check get this
letter instead: what finished, with which result, the reason of a failure, the OLX validation list
and a button to the Studio page. Other tasks keep the stock letter (signals.py).

A course import / export gets no letter here: it is the notification «Импорт или экспорт курса»
(robbo_events.py), and its settings decide whether a letter comes — «Сразу», in a digest or none
(email is off by default).

Copyright (C) 2026 Robbo <https://robbo.ru>
SPDX-License-Identifier: AGPL-3.0-only
Part of the Robbo Open edX distribution. See NOTICE at repository root.
"""
import json
import logging
import re

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils.html import escape
from edx_django_utils.monitoring import set_code_owner_attribute
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from opaque_keys.edx.locator import LibraryLocator

log = logging.getLogger(__name__)

TASKS = (
    ('export', re.compile(r'^Export of (?P<key>\S+)$')),
    ('import', re.compile(r'^Import of (?P<key>\S+) from (?P<file>.+)$')),
    ('linkcheck', re.compile(r'^Broken link check of (?P<key>\S+)$')),
)

TEXTS = {
    'ru': {
        'what': {
            ('export', 'library'): 'Экспорт библиотеки', ('import', 'library'): 'Импорт библиотеки',
            ('linkcheck', 'course'): 'Проверка ссылок в курсе',
        },
        'result': {
            ('export', 'Succeeded'): 'готов', ('import', 'Succeeded'): 'завершён',
            ('linkcheck', 'Succeeded'): 'завершена',
            ('export', 'Failed'): 'не удался', ('import', 'Failed'): 'не удался',
            ('linkcheck', 'Failed'): 'не удалась',
            ('export', 'Canceled'): 'отменён', ('import', 'Canceled'): 'отменён',
            ('linkcheck', 'Canceled'): 'отменена',
        },
        'hint': {
            ('export', 'Succeeded'): 'Архив можно скачать на странице экспорта в Студии.',
            ('import', 'Succeeded'): 'Содержимое обновлено из файла {file}.',
            ('linkcheck', 'Succeeded'): 'Найденные неработающие ссылки — на странице проверки в Студии.',
            'Failed': 'Подробности и повторный запуск — в Студии.',
            'Canceled': 'Задачу можно запустить снова в Студии.',
        },
        'button': {'export': 'Скачать архив', 'import': 'Открыть в Студии', 'linkcheck': 'Открыть результаты',
                   'other': 'Открыть в Студии'},
        'reason': 'Причина',
        'errors': 'Ошибки в содержимом',
        'warnings': 'Предупреждения',
        'note': 'Вы получили это письмо, потому что запустили эту задачу в Студии.',
    },
    'en': {
        'what': {
            ('export', 'library'): 'Library export', ('import', 'library'): 'Library import',
            ('linkcheck', 'course'): 'Link check of the course',
        },
        'result': {
            ('export', 'Succeeded'): 'is ready', ('import', 'Succeeded'): 'is complete',
            ('linkcheck', 'Succeeded'): 'is complete',
            ('export', 'Failed'): 'failed', ('import', 'Failed'): 'failed', ('linkcheck', 'Failed'): 'failed',
            ('export', 'Canceled'): 'was canceled', ('import', 'Canceled'): 'was canceled',
            ('linkcheck', 'Canceled'): 'was canceled',
        },
        'hint': {
            ('export', 'Succeeded'): 'Download the archive on the export page in Studio.',
            ('import', 'Succeeded'): 'The content was updated from {file}.',
            ('linkcheck', 'Succeeded'): 'The broken links found are on the link check page in Studio.',
            'Failed': 'See the details and try again in Studio.',
            'Canceled': 'You can start the task again in Studio.',
        },
        'button': {'export': 'Download the archive', 'import': 'Open in Studio', 'linkcheck': 'Open the results',
                   'other': 'Open in Studio'},
        'reason': 'Reason',
        'errors': 'Errors in the content',
        'warnings': 'Warnings',
        'note': 'You get this email because you started this task in Studio.',
    },
}


def parse(name):
    """(operation, key, file) for the tasks this letter covers, None for the rest."""
    for operation, pattern in TASKS:
        match = pattern.match(name or '')
        if match:
            try:
                key = CourseKey.from_string(match['key'])
            except InvalidKeyError:
                return None
            if operation == 'linkcheck' and isinstance(key, LibraryLocator):
                return None
            return operation, key, match.groupdict().get('file') or ''
    return None


def handles(status):
    return parse(status.name) is not None


def left_to_notifications(status):
    """A course import / export: the notification settings decide about the letter (no letter here)."""
    operation, key, _ = parse(status.name)
    return operation in ('export', 'import') and not isinstance(key, LibraryLocator)


def _title(key):
    if isinstance(key, LibraryLocator):
        from xmodule.modulestore.django import modulestore  # pylint: disable=import-outside-toplevel
        try:
            return modulestore().get_library(key).display_name
        except Exception:  # pylint: disable=broad-except
            return str(key)
    from openedx.core.djangoapps.notifications.robbo_events import course_name  # pylint: disable=import-outside-toplevel
    return course_name(key)


def _url(operation, key):
    studio = (getattr(settings, 'CMS_ROOT_URL', '') or f"//{getattr(settings, 'CMS_BASE', '')}").rstrip('/')
    if isinstance(key, LibraryLocator):
        return f'{studio}/{operation}/{key}' if operation in ('export', 'import') else f'{studio}/library/{key}'
    from cms.djangoapps.contentstore import utils  # pylint: disable=import-outside-toplevel
    mfe = {'export': utils.get_export_url, 'import': utils.get_import_url,
           'linkcheck': utils.get_optimizer_url}[operation](key)
    return mfe or (f'{studio}/{operation}/{key}' if operation != 'linkcheck' else f'{studio}/course/{key}')


def render(status, lang, olx_validation_text=None):
    """(subject, text, html) of the letter."""
    # pylint: disable=import-outside-toplevel
    from user_tasks.models import UserTaskArtifact
    from openedx.core.djangoapps.notifications.email.robbo_layout import GREEN_DARK, MUTED, TEXT, button, frame
    texts = TEXTS[lang]
    operation, key, file = parse(status.name)
    state = status.state if status.state in ('Succeeded', 'Failed', 'Canceled') else 'Failed'
    kind = 'library' if isinstance(key, LibraryLocator) else 'course'
    title = _title(key)
    headline = f"{texts['what'][(operation, kind)]} «{title}» {texts['result'][(operation, state)]}"
    hint = (texts['hint'].get((operation, state)) or texts['hint'].get(state, '')).format(file=file)
    reason = ''
    if state == 'Failed':
        error = UserTaskArtifact.objects.filter(status=status, name='Error').first()
        reason = (error.text or '').strip()[:500] if error else ''
    validation = {}
    if olx_validation_text:
        try:
            validation = json.loads(olx_validation_text)
        except ValueError:
            validation = {}
    url = _url(operation, key)
    label = texts['button'][operation] if state == 'Succeeded' else texts['button']['other']

    lists = ''
    plain_lists = []
    for name in ('errors', 'warnings'):
        items = validation.get(name) or []
        if items:
            lists += (f'<p style="margin:16px 0 4px;color:{TEXT};font-size:14px;font-weight:700">'
                      f'{escape(texts[name])} · {len(items)}</p><ol style="margin:0;padding-left:20px;color:{TEXT};'
                      f'font-size:13px;line-height:1.5">' + ''.join(f'<li>{escape(item)}</li>' for item in items)
                      + '</ol>')
            plain_lists += [f'{texts[name]} ({len(items)}):'] + [f'{i}. {item}' for i, item in enumerate(items, 1)]
    inner = (
        f'<p style="margin:0 0 8px;color:{GREEN_DARK};font-size:13px;font-weight:700">'
        f'{"Студия" if lang == "ru" else "Studio"}</p>'
        f'<p style="margin:0 0 8px;color:{TEXT};font-size:16px;line-height:1.5"><strong>{escape(headline)}</strong></p>'
        + (f'<p style="margin:0 0 8px;color:{TEXT};font-size:14px;line-height:1.5">'
           f'{escape(texts["reason"])}: {escape(reason)}</p>' if reason else '')
        + (f'<p style="margin:0 0 20px;color:{MUTED};font-size:14px;line-height:1.5">{escape(hint)}</p>' if hint else '')
        + button(url, label) + lists
    )
    html = frame(lang, inner, texts['note'])
    text = '\n\n'.join(filter(None, [
        headline, f'{texts["reason"]}: {reason}' if reason else '', hint, url, '\n'.join(plain_lists),
    ]))
    return headline, text, html


@shared_task(ignore_result=True)
@set_code_owner_attribute
def send_robbo_task_email(status_uuid, olx_validation_text=None):
    """Sends the letter about a finished Studio task to the user who started it."""
    # pylint: disable=import-outside-toplevel
    from user_tasks.models import UserTaskStatus
    from openedx.core.djangoapps.notifications.robbo_texts import lang_of, notification_from_email
    from openedx.core.djangoapps.user_api.models import UserPreference
    status = UserTaskStatus.objects.filter(uuid=status_uuid).select_related('user').first()
    if status is None or not status.user.email or not handles(status) or left_to_notifications(status):
        return
    lang = lang_of(UserPreference.get_value(status.user, 'pref-lang') or settings.LANGUAGE_CODE)
    subject, text, html = render(status, lang, olx_validation_text)
    message = EmailMultiAlternatives(subject, text, notification_from_email(), [status.user.email])
    message.attach_alternative(html, 'text/html')
    message.send()
    log.info('Robbo: task letter sent for %s', status.name)
