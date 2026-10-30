# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (human-readable errors). See NOTICE at repository root.
"""
Error pages that views render themselves instead of raising (docs/human-errors.md §7 in the meta
repo): the Django handlers never see them, so the theme redraws each one as the error block of
``_error_block.html`` with texts from ``PAGES``. Templates: the same path in
``themes/robbo-theme/lms/templates`` (``robbo_payments/error.html`` is ours and calls this directly).

A page that answers a crash the view caught itself writes the journal here (``journal=True``):
the robbo_errors middleware only sees exceptions that leave the view. Inside a transaction the
write waits for the middleware (``run_deferred_journal``): the view may roll it back, as
``confirm_email_change`` does, and the case would go with it.
"""

import logging
import sys
import traceback
from collections import namedtuple
from functools import partial

from crum import get_current_request
from django.conf import settings
from django.db import transaction
from django.urls import reverse

from lms.djangoapps.robbo_changelog.labels import current_lang, pick

from .pages import page_context
from .responses import journal_request

log = logging.getLogger(__name__)

# action: a key of ACTIONS (a link) or one of the block's own: home, reload, back, login
Page = namedtuple('Page', 'code title message action journal', defaults=('home', False))

ACTIONS = {
    'account': (lambda **params: settings.ACCOUNT_MICROFRONTEND_URL or '/account/settings',
                {'ru': 'Открыть настройки учётной записи', 'en': 'Open account settings'}),
    'dashboard': (lambda **params: reverse('dashboard'),
                  {'ru': 'Перейти к моим курсам', 'en': 'Go to my courses'}),
    'catalog': (lambda **params: reverse('courses'),
                {'ru': 'Открыть каталог курсов', 'en': 'Open the course catalog'}),
    'course_about': (lambda course_key, **params: reverse('about_course', args=[str(course_key)]),
                     {'ru': 'Открыть страницу курса', 'en': 'Open the course page'}),
}

SERVER_ERROR_MESSAGE = {
    'ru': 'Это ошибка на нашей стороне, мы её записали. Обновите страницу через минуту.',
    'en': 'This is an error on our side, and we have logged it. Reload the page in a minute.',
}

PAGES = {
    # common/djangoapps/student/views/management.py: confirm_email_change, activate_secondary_email
    'email_key': Page('NOT-FOUND', {
        'ru': 'Ссылка для смены почты не работает',
        'en': 'The email change link doesn\'t work',
    }, {
        'ru': 'Возможно, она устарела или по ней уже переходили. Проверьте адрес почты в настройках '
              'учётной записи и, если нужно, запросите смену ещё раз.',
        'en': 'It may have expired or been used already. Check your email address in the account settings '
              'and request the change again if needed.',
    }, 'account'),
    'email_exists': Page('BAD-INPUT', {
        'ru': 'Эта почта уже занята',
        'en': 'This email is already in use',
    }, {
        'ru': 'Новый адрес уже указан в другой учётной записи, поэтому почта не изменилась. '
              'Укажите в настройках другой адрес.',
        'en': 'The new address already belongs to another account, so your email has not changed. '
              'Enter a different address in the settings.',
    }, 'account'),
    'email_change_failed': Page('SRV-ERROR', {
        'ru': 'Не удалось сменить почту',
        'en': 'Couldn\'t change the email',
    }, {
        'ru': 'Не получилось отправить письмо на адрес {email}, поэтому почта не изменилась. '
              'Откройте ссылку из письма ещё раз через несколько минут.',
        'en': 'We couldn\'t send an email to {email}, so your email has not changed. '
              'Open the link from the email again in a few minutes.',
    }, 'account', True),

    # lms/djangoapps/courseware: a course tab or a block of the course pages crashed
    'courseware_error': Page('SRV-ERROR', {
        'ru': 'Не удалось открыть страницу курса',
        'en': 'Couldn\'t open the course page',
    }, SERVER_ERROR_MESSAGE, 'reload', True),
    'courseware_fragment': Page('SRV-ERROR', {
        'ru': 'Этот раздел временно не открывается',
        'en': 'This section is temporarily unavailable',
    }, SERVER_ERROR_MESSAGE, 'reload', True),

    # common/djangoapps/course_modes/views.py: choosing the enrollment mode failed
    'enroll_closed': Page('ACCESS-DENIED', {
        'ru': 'Не удалось записаться на курс',
        'en': 'Couldn\'t enroll in the course',
    }, {
        'ru': 'Запись на курс «{course_name}» закрыта. Выберите другой курс в каталоге.',
        'en': 'Enrollment in «{course_name}» is closed. Choose another course in the catalog.',
    }, 'catalog'),
    'enroll_failed': Page('BAD-INPUT', {
        'ru': 'Не удалось записаться на курс',
        'en': 'Couldn\'t enroll in the course',
    }, {
        'ru': 'Этот вариант записи на курс «{course_name}» недоступен. Вернитесь назад и выберите другой.',
        'en': 'This enrollment option for «{course_name}» is not available. Go back and choose another one.',
    }, 'back'),

    # lms/djangoapps/robbo_payments/views/checkout.py
    'payment_details_missing': Page('BAD-INPUT', {
        'ru': 'Не удалось перейти к оплате',
        'en': 'Couldn\'t go to the payment',
    }, {
        'ru': 'В ссылке на оплату не хватает данных о курсе. Откройте оплату заново со страницы курса.',
        'en': 'The payment link lacks the course details. Open the payment again from the course page.',
    }, 'dashboard'),
    'payment_unavailable': Page('NOT-FOUND', {
        'ru': 'Полный доступ к курсу не продаётся',
        'en': 'Full access to this course is not for sale',
    }, {
        'ru': 'Сейчас этот курс нельзя оплатить. Если вы ждали оплату, напишите в поддержку.',
        'en': 'This course can\'t be paid for now. If you expected to pay, contact support.',
    }, 'dashboard'),
    'payment_not_enrolled': Page('ACCESS-DENIED', {
        'ru': 'Сначала запишитесь на курс',
        'en': 'Enroll in the course first',
    }, {
        'ru': 'Полный доступ можно купить только к курсу, на который вы записаны. '
              'Запишитесь на странице курса и вернитесь к оплате.',
        'en': 'Full access can only be bought for a course you are enrolled in. '
              'Enroll on the course page and come back to the payment.',
    }, 'course_about'),
    'payment_cannot_upgrade': Page('BAD-INPUT', {
        'ru': 'Полный доступ к этому курсу купить нельзя',
        'en': 'Full access to this course can\'t be bought',
    }, {
        'ru': 'Ваш вариант записи на курс не переводится на полный доступ. Напишите в поддержку.',
        'en': 'Your enrollment option can\'t be upgraded to full access. Contact support.',
    }, 'dashboard'),
    'payment_not_configured': Page('SRV-ERROR', {
        'ru': 'Оплата временно недоступна',
        'en': 'Payment is temporarily unavailable',
    }, {
        'ru': 'Приём оплаты на сайте не настроен. Мы записали ошибку; напишите в поддержку и укажите код.',
        'en': 'Payments are not set up on the site. We have logged the error; contact support and give the code.',
    }, 'dashboard', True),
    'payment_failed': Page('SRV-ERROR', {
        'ru': 'Не удалось начать оплату',
        'en': 'Couldn\'t start the payment',
    }, {
        'ru': 'Платёжная система не ответила. Деньги не списаны. Попробуйте ещё раз через несколько минут.',
        'en': 'The payment service didn\'t answer. No money was charged. Try again in a few minutes.',
    }, 'dashboard', True),

    # lms/djangoapps/robbo_payments/views/certificate.py
    'certificate_unavailable': Page('NOT-FOUND', {
        'ru': 'Сертификат этого курса не продаётся',
        'en': 'The certificate of this course is not for sale',
    }, {
        'ru': 'Сейчас сертификат этого курса нельзя оплатить. Если вы ждали оплату, напишите в поддержку.',
        'en': 'The certificate of this course can\'t be paid for now. If you expected to pay, contact support.',
    }, 'dashboard'),
    'certificate_not_enrolled': Page('ACCESS-DENIED', {
        'ru': 'Сначала запишитесь на курс',
        'en': 'Enroll in the course first',
    }, {
        'ru': 'Сертификат можно оформить только по курсу, на который вы записаны и который прошли.',
        'en': 'A certificate can only be bought for a course you are enrolled in and have passed.',
    }, 'course_about'),
}


def _write(write):
    try:
        write()
    except Exception:  # pylint: disable=broad-except
        log.exception('robbo_errors: could not journal an error page')


def run_deferred_journal(request):
    """Journal what ``build`` put off inside a transaction; the middleware calls it after the view."""
    for write in request.__dict__.pop('_robbo_deferred_journal', []):
        _write(write)


def build(request, code, title, message, action='home', action_url=None, action_label=None,
          journal=False, developer_message=''):
    """
    ``robbo_error`` of ``_error_block.html``: ``code`` of the catalog with its own title and message.
    ``journal`` writes the case with the traceback being handled, if any.
    """
    if journal:
        trace = traceback.format_exc() if sys.exc_info()[0] is not None else ''
        write = partial(journal_request, request, code, 500,
                        developer_message=developer_message or title, traceback=trace)
        if transaction.get_connection().in_atomic_block:
            request.__dict__.setdefault('_robbo_deferred_journal', []).append(write)
        else:
            _write(write)
    error = page_context(request, code)['robbo_error']
    error.update(title=title, message=message, action=action)
    if action_url:
        error.update(action='link', action_url=action_url, action_label=action_label)
    return error


def error_for(key, request=None, **params):
    """
    ``robbo_error`` for page ``key`` of ``PAGES``; ``params`` fill the {placeholders} of the message
    and the action link. Once per request and key: a page asks for it in the title and the body, and
    the journal must get one case.
    """
    request = request or get_current_request()
    cache = request.__dict__.setdefault('_robbo_upstream_errors', {})
    if key not in cache:
        page = PAGES[key]
        lang = current_lang()
        action_url = action_label = None
        if page.action in ACTIONS:
            url, label = ACTIONS[page.action]
            action_url, action_label = url(**params), pick(label, lang)
        cache[key] = build(
            request, page.code, pick(page.title, lang).format(**params), pick(page.message, lang).format(**params),
            action=page.action if page.action not in ACTIONS else 'home',
            action_url=action_url, action_label=action_label, journal=page.journal,
            developer_message=key,
        )
    return cache[key]
