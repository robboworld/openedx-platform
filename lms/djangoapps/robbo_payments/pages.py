# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (YooKassa checkout). See NOTICE at repository root.
"""
What the checkout and receipt pages show (templates robbo_payments/checkout.html, receipt.html).

Texts are Russian and English here, not in the theme .po: ``pick`` takes the learner's language.
What full access includes is computed from the course settings (paid content, a certificate free for
full access), so the checkout page and the Learning MFE «Полный доступ» tab
(course_home_api course metadata ``robbo_full_access_includes``) never promise what the course
does not give.
"""

from datetime import timedelta

from django.utils import timezone

from lms.djangoapps.robbo_changelog.labels import format_date, pick
from openedx.features.course_experience.url_helpers import get_learning_mfe_home_url

from .constants import OrderStatus, Product
from .utils import format_checkout_price_display

T = {
    'eyebrow': {'ru': 'Оформление заказа', 'en': 'Checkout'},
    'product_course_access': {'ru': 'Полный доступ к курсу', 'en': 'Full access to the course'},
    'product_certificate': {'ru': 'Сертификат о прохождении курса', 'en': 'Course completion certificate'},
    'includes_title': {'ru': 'Что вы получите', 'en': 'What you get'},
    'include_paid_content': {
        'ru': 'Все материалы курса, в том числе закрытые разделы и задания',
        'en': 'All course materials, including locked sections and assignments',
    },
    'include_certificate': {
        'ru': 'Сертификат о прохождении курса без доплаты',
        'en': 'The course completion certificate at no extra cost',
    },
    'include_full_access': {'ru': 'Полный доступ ко всему курсу', 'en': 'Full access to the whole course'},
    'include_cert_progress': {
        'ru': 'Сертификат появится на странице прогресса через пару минут после оплаты',
        'en': 'The certificate appears on the Progress page a few minutes after the payment',
    },
    'include_cert_link': {
        'ru': 'Сертификат открывается по ссылке — её можно отправить или распечатать сертификат',
        'en': 'The certificate opens by a link — share it or print the certificate',
    },
    'total': {'ru': 'К оплате', 'en': 'Total'},
    'pay': {'ru': 'Перейти к оплате', 'en': 'Proceed to payment'},
    'pay_note': {
        'ru': 'Оплата проходит на защищённой странице ЮKassa.',
        'en': 'You pay on the secure YooKassa page.',
    },
    'pay_note_email': {
        'ru': 'Оплата проходит на защищённой странице ЮKassa. Чек придёт на {email}.',
        'en': 'You pay on the secure YooKassa page. The receipt is sent to {email}.',
    },
    'not_configured': {
        'ru': 'Оплата временно недоступна. Попробуйте позже.',
        'en': 'Payment is temporarily unavailable. Try again later.',
    },
    'back_to_course': {'ru': 'Вернуться к курсу', 'en': 'Back to the course'},

    'paid_title': {'ru': 'Оплата прошла', 'en': 'Payment successful'},
    'paid_course_access': {
        'ru': 'Полный доступ к курсу открыт. Можно продолжать обучение.',
        'en': 'Full access to the course is open. You can go on learning.',
    },
    'paid_certificate': {
        'ru': 'Сертификат появится на странице прогресса через пару минут.',
        'en': 'The certificate will appear on the Progress page in a few minutes.',
    },
    'pending_title': {'ru': 'Оплата обрабатывается', 'en': 'Payment is processing'},
    'pending_body': {
        'ru': 'Обычно это занимает меньше минуты. Страница обновится сама.',
        'en': 'It usually takes less than a minute. The page will refresh itself.',
    },
    'pending_stale_body': {
        'ru': 'Платёж обрабатывается дольше обычного. Если деньги списались, а доступ не открылся, '
              'напишите в поддержку и укажите номер заказа.',
        'en': 'The payment is taking longer than usual. If the money was charged and access did not open, '
              'contact support and give the order number.',
    },
    'failed_title': {'ru': 'Оплата не прошла', 'en': 'The payment did not go through'},
    'failed_body': {
        'ru': 'Деньги не списаны. Можно попробовать ещё раз — например, другой картой.',
        'en': 'No money was charged. You can try again, for example with another card.',
    },
    'refunded_title': {'ru': 'Оплата возвращена', 'en': 'The payment was refunded'},
    'refunded_body': {
        'ru': 'Деньги вернулись тем же способом, которым вы платили.',
        'en': 'The money went back the way you paid.',
    },
    'row_course': {'ru': 'Курс', 'en': 'Course'},
    'row_product': {'ru': 'Что оплачено', 'en': 'Purchase'},
    'row_amount': {'ru': 'Сумма', 'en': 'Amount'},
    'row_order': {'ru': 'Номер заказа', 'en': 'Order number'},
    'row_date': {'ru': 'Дата', 'en': 'Date'},
    'go_course': {'ru': 'Перейти к курсу', 'en': 'Go to the course'},
    'go_progress': {'ru': 'Открыть страницу прогресса', 'en': 'Open the Progress page'},
    'refresh': {'ru': 'Обновить', 'en': 'Refresh'},
    'retry': {'ru': 'Попробовать ещё раз', 'en': 'Try again'},
    'help_before': {'ru': 'Если что-то пошло не так, ', 'en': 'If something went wrong, '},
    'help_link': {'ru': 'напишите в поддержку', 'en': 'contact support'},
    'help_after': {'ru': ' и укажите номер заказа.', 'en': ' and give the order number.'},
}

# A pending receipt refreshes itself this long; after that it says to contact support
PENDING_REFRESH_WINDOW = timedelta(minutes=30)
PENDING_REFRESH_SECONDS = 10


def text(key, **params):
    value = pick(T[key])
    return value.format(**params) if params else value


def full_access_includes(course_key):
    """
    What full access gives in this course: ``paid_content`` (the course has locked parts),
    ``certificate`` (a paid certificate that is free with full access). Empty — just full access.
    """
    includes = []
    from lms.djangoapps.robbo_paid_content.policy import get_policy
    if get_policy(course_key) is not None:
        includes.append('paid_content')
    from lms.djangoapps.robbo_certificates.offers import active_offer
    offer = active_offer(course_key)
    if offer is not None and 'verified' in (offer.free_for_modes or []):
        includes.append('certificate')
    return includes


def checkout_context(*, product, course_key, course_name, price_display, email, checkout_url, yookassa_configured,
                     sku=None):
    """Context of robbo_payments/checkout.html for either product."""
    if product == Product.CERTIFICATE:
        includes = [text('include_cert_progress'), text('include_cert_link')]
    else:
        keys = full_access_includes(course_key)
        includes = [text(f'include_{key}') for key in keys] or [text('include_full_access')]
    return {
        'texts': {key: pick(value) for key, value in T.items()},
        'product_label': text('product_certificate' if product == Product.CERTIFICATE else 'product_course_access'),
        'course_name': course_name,
        'course_url': get_learning_mfe_home_url(course_key, 'progress' if product == Product.CERTIFICATE else 'home'),
        'includes': includes,
        'price_display': price_display,
        'pay_note': text('pay_note_email', email=email) if email else text('pay_note'),
        'checkout_url': checkout_url,
        'yookassa_configured': yookassa_configured,
        'sku': sku,
        'course_run_key': str(course_key),
    }


def receipt_context(order, course_name, retry_url):
    """Context of robbo_payments/receipt.html: the state of the order and what to do next."""
    from lms.djangoapps.robbo_errors import catalog

    certificate = order.product == Product.CERTIFICATE
    course_url = get_learning_mfe_home_url(order.course_key, 'home')
    progress_url = get_learning_mfe_home_url(order.course_key, 'progress')
    actions = []
    auto_refresh = False
    if order.status == OrderStatus.PAID:
        state, title = 'paid', text('paid_title')
        body = text('paid_certificate' if certificate else 'paid_course_access')
        actions = [(progress_url, text('go_progress')) if certificate else (course_url, text('go_course'))]
    elif order.status == OrderStatus.PENDING:
        state, title = 'pending', text('pending_title')
        auto_refresh = timezone.now() - order.created_at < PENDING_REFRESH_WINDOW
        body = text('pending_body' if auto_refresh else 'pending_stale_body')
        actions = [('', text('refresh')), (course_url, text('back_to_course'))]
    elif order.status == OrderStatus.REFUNDED:
        state, title, body = 'refunded', text('refunded_title'), text('refunded_body')
        actions = [(course_url, text('go_course'))]
    else:
        state, title, body = 'failed', text('failed_title'), text('failed_body')
        actions = [(retry_url, text('retry'))] if retry_url else []
        actions.append((course_url, text('back_to_course')))

    return {
        'state': state,
        'title': title,
        'body': body,
        'rows': [
            (text('row_course'), course_name),
            (text('row_product'), text('product_certificate' if certificate else 'product_course_access')),
            (text('row_amount'), format_checkout_price_display(order.amount, order.currency)),
            (text('row_order'), order.order_number),
            (text('row_date'), format_date(timezone.localtime(order.created_at).date())),
        ],
        'actions': actions,
        'auto_refresh_seconds': PENDING_REFRESH_SECONDS if auto_refresh else None,
        'help': (text('help_before'), catalog.support_url(), text('help_link'), text('help_after')),
    }
