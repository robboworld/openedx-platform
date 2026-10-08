# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (site changelog). See NOTICE at repository root.
"""
Interface texts of «Что нового», in Russian and English like the entries themselves.

The page picks the user's active language (``current_lang``), so labels live next to the
entries instead of gettext catalogs. Also used by the LMS and Studio footers for the link.
"""

from django.conf import settings
from django.utils.translation import get_language

PAGE = {
    'title': {'ru': 'Что нового', 'en': "What's new"},
    'lede': {
        'ru': 'Рассказываем, что изменилось на платформе: сначала главное, в конце — мелкие правки.',
        'en': 'What has changed on the platform: the main things first, small fixes at the end.',
    },
    'staff_note': {
        'ru': 'Изменения с пометкой «Для …» видит только персонал с этой ролью, учащимся они не показываются.',
        'en': 'Changes marked “For …” are shown only to staff with that role, never to learners.',
    },
    'filters': {'ru': 'Фильтр изменений', 'en': 'Filter changes'},
    'section_filter': {'ru': 'Раздел', 'en': 'Section'},
    'audience_filter': {'ru': 'Для кого', 'en': 'For whom'},
    'any_section': {'ru': 'Все разделы', 'en': 'All sections'},
    'any_audience': {'ru': 'Все', 'en': 'Everyone'},
    'audience_all': {'ru': 'Для всех', 'en': 'For everyone'},
    'action': {'ru': 'Что нужно сделать', 'en': 'What to do'},
    'version': {'ru': 'Версия', 'en': 'Version'},
    'empty': {'ru': 'Здесь пока нет изменений.', 'en': 'No changes here yet.'},
    'empty_filtered': {'ru': 'По этому фильтру изменений нет.', 'en': 'No changes match this filter.'},
    'reset_filter': {'ru': 'Показать все изменения', 'en': 'Show all changes'},
    'reset': {'ru': 'Сбросить', 'en': 'Reset'},
    'apply': {'ru': 'Показать', 'en': 'Apply'},
    # Header button and panel.
    'button_unread': {'ru': 'Что нового, непрочитанных: {count}', 'en': "What's new, {count} unread"},
    'unread': {'ru': 'Новое для вас', 'en': 'New for you'},
    'close': {'ru': 'Закрыть', 'en': 'Close'},
    'all_changes': {'ru': 'Все изменения', 'en': 'All changes'},
    'loading': {'ru': 'Загружаем изменения…', 'en': 'Loading changes…'},
    'error': {'ru': 'Не удалось загрузить изменения. Попробуйте позже.',
              'en': 'Could not load the changes. Please try again later.'},
}

IMPORTANCE = {
    'major': {'ru': 'Главное', 'en': 'Highlights'},
    'notable': {'ru': 'Заметные улучшения', 'en': 'Improvements'},
    'minor': {'ru': 'Мелкие правки', 'en': 'Small fixes'},
}

KINDS = {
    'important': {'ru': 'Важное', 'en': 'Important'},
    'new': {'ru': 'Новое', 'en': 'New'},
    'improved': {'ru': 'Улучшено', 'en': 'Improved'},
    'fixed': {'ru': 'Исправлено', 'en': 'Fixed'},
}

AUDIENCES = {
    'authors': {'ru': 'Для авторов курсов', 'en': 'For course authors'},
    'teachers': {'ru': 'Для преподавателей', 'en': 'For teachers'},
    'platform_staff': {'ru': 'Для сотрудников платформы', 'en': 'For platform staff'},
    'platform_admins': {'ru': 'Для администраторов платформы', 'en': 'For platform administrators'},
}

SECTIONS = {
    'platform': {'ru': 'Вся платформа', 'en': 'Whole platform'},
    'home': {'ru': 'Главная и каталог', 'en': 'Home and catalog'},
    'dashboard': {'ru': 'Мои курсы', 'en': 'My courses'},
    'courseware': {'ru': 'Прохождение курса', 'en': 'Course content'},
    'assignments': {'ru': 'Задания с развёрнутым ответом', 'en': 'Open response assignments'},
    'certificates': {'ru': 'Сертификаты', 'en': 'Certificates'},
    'payments': {'ru': 'Оплата', 'en': 'Payments'},
    'account': {'ru': 'Профиль и настройки', 'en': 'Profile and settings'},
    'auth': {'ru': 'Вход и регистрация', 'en': 'Sign in and registration'},
    'discussions': {'ru': 'Обсуждения', 'en': 'Discussions'},
    'emails': {'ru': 'Письма', 'en': 'Emails'},
    'personal_account': {'ru': 'Личный кабинет', 'en': 'Personal account'},
    'studio': {'ru': 'Редактор курсов', 'en': 'Course editor'},
    'instructor': {'ru': 'Панель преподавателя', 'en': 'Instructor dashboard'},
}

MONTHS = {
    'ru': ('января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа',
           'сентября', 'октября', 'ноября', 'декабря'),
    'en': ('January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
           'September', 'October', 'November', 'December'),
}


def current_lang():
    """``ru`` or ``en``: the user's active language, else the site default (``LANGUAGE_CODE``)."""
    for lang in (get_language(), settings.LANGUAGE_CODE):
        code = (lang or '').lower().split('-')[0]
        if code in ('ru', 'en'):
            return code
    return 'ru'


def pick(texts, lang=None):
    """One language out of a ``{'ru': …, 'en': …}`` mapping."""
    return texts[lang or current_lang()]


def format_date(date, lang=None):
    """«7 октября 2026» / «7 October 2026»."""
    lang = lang or current_lang()
    return f'{date.day} {MONTHS[lang][date.month - 1]} {date.year}'


def unread_summary(count, lang=None):
    """Panel subtitle: «3 новых изменения» / «3 new changes», or that there is nothing new."""
    lang = lang or current_lang()
    if lang == 'en':
        return f'{count} new change' + ('' if count == 1 else 's') if count else "You're all caught up"
    if not count:
        return 'Новых изменений нет'
    tens, units = count % 100, count % 10
    if units == 1 and tens != 11:
        return f'{count} новое изменение'
    if 2 <= units <= 4 and not 12 <= tens <= 14:
        return f'{count} новых изменения'
    return f'{count} новых изменений'
