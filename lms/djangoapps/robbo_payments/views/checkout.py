# Copyright (C) 2024-2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (YooKassa checkout). See NOTICE at repository root.

"""Checkout views compatible with legacy ecommerce /basket/add/ URLs."""

import logging

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods

from common.djangoapps.course_modes.models import CourseMode
from common.djangoapps.edxmako.shortcuts import render_to_response
from common.djangoapps.student.models import CourseEnrollment
from openedx.features.course_experience.url_helpers import make_learning_mfe_courseware_url

from ..models import Order
from ..processors.yookassa import (
    YooKassaNotConfigured,
    YooKassaPaymentError,
    create_redirect_payment,
    is_yookassa_configured,
    new_idempotency_key,
)
from ..services.catalog import (
    CatalogError,
    get_first_sku_from_query,
    resolve_verified_product,
)
from ..utils import payments_enabled

log = logging.getLogger(__name__)


def _require_payments_enabled():
    if not payments_enabled():
        raise Http404('Payments are not enabled')


def _customer_email(user):
    return user.email or ''


@login_required
@require_http_methods(['GET', 'POST'])
def basket_add(request):
    """
    Checkout entry point: /basket/add/?sku=...&course_run_key=...

    GET renders confirmation; POST creates order and redirects to YooKassa.
    """
    _require_payments_enabled()

    sku = get_first_sku_from_query(request.GET.get('sku') or request.POST.get('sku'))
    course_run_key = request.GET.get('course_run_key') or request.POST.get('course_run_key')

    if not sku or not course_run_key:
        return render_to_response('robbo_payments/error.html', {
            'error_message': _('Не указаны данные курса или продукта для оплаты.'),
        })

    try:
        product = resolve_verified_product(course_run_key, sku)
    except CatalogError as exc:
        log.warning('Checkout catalog error for user=%s: %s', request.user.id, exc)
        return render_to_response('robbo_payments/error.html', {
            'error_message': _('Этот продукт недоступен для покупки.'),
        })

    enrollment = CourseEnrollment.get_enrollment(request.user, product.course_key)
    if enrollment is None or not enrollment.is_active:
        return render_to_response('robbo_payments/error.html', {
            'error_message': _('Сначала нужно записаться на курс, чтобы оформить полный доступ.'),
        })

    if enrollment.mode == CourseMode.VERIFIED:
        return redirect(make_learning_mfe_courseware_url(str(product.course_key)))

    if enrollment.mode not in (CourseMode.AUDIT, CourseMode.HONOR):
        return render_to_response('robbo_payments/error.html', {
            'error_message': _('Эту запись нельзя перевести на полный доступ.'),
        })

    if request.method == 'GET':
        return render_to_response('robbo_payments/checkout.html', {
            'product': product,
            'course_run_key': str(product.course_key),
            'sku': product.sku,
            'checkout_url': reverse('robbo_payments:basket_add'),
            'yookassa_configured': is_yookassa_configured(),
        })

    if not is_yookassa_configured():
        return render_to_response('robbo_payments/error.html', {
            'error_message': _('Платёжный сервис не настроен. Обратитесь в поддержку.'),
        })

    order = Order.objects.create(
        user=request.user,
        course_key=product.course_key,
        sku=product.sku,
        amount=product.amount,
        currency=product.currency,
        idempotency_key=new_idempotency_key(),
    )

    description = _('Полный доступ: {course_name}').format(course_name=product.course_name)
    try:
        confirmation_url = create_redirect_payment(
            order,
            str(description),
            _customer_email(request.user),
            request,
        )
    except (YooKassaNotConfigured, YooKassaPaymentError):
        order.delete()
        return render_to_response('robbo_payments/error.html', {
            'error_message': _('Не удалось начать оплату. Попробуйте позже.'),
        })

    return redirect(confirmation_url)
