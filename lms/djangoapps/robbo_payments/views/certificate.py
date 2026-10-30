# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (paid certificates). See NOTICE at repository root.

"""Checkout of a paid certificate: /robbo/certificates/buy/<course_id>/."""

import logging

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from ipware import get_client_ip
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey

from common.djangoapps.edxmako.shortcuts import render_to_response
from common.djangoapps.student.models import CourseEnrollment
from lms.djangoapps.grades.api import CourseGradeFactory
from lms.djangoapps.robbo_certificates import offers
from lms.djangoapps.robbo_changelog.labels import pick
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from openedx.features.course_experience.url_helpers import get_learning_mfe_home_url

from ..constants import OrderStatus, Product
from ..models import Order
from ..pages import checkout_context
from ..processors.yookassa import (
    YooKassaNotConfigured,
    YooKassaPaymentError,
    create_redirect_payment,
    is_yookassa_configured,
    new_idempotency_key,
)
from ..services.sync import sync_order_from_yookassa
from ..utils import format_checkout_price_display, payments_enabled
from .checkout import _customer_email, _error_page

log = logging.getLogger(__name__)

TEXTS = {
    'description': {'ru': 'Сертификат: {course_name}', 'en': 'Certificate: {course_name}'},
}


def _progress_redirect(course_key):
    return redirect(get_learning_mfe_home_url(course_key, 'progress'))


def _sync_pending_orders(user, course_key, request):
    """
    Refresh started certificate payments from YooKassa before a new one: a learner who paid in
    another tab (webhook not here yet) must not pay twice. Returns a paid order, if any.
    """
    client_ip, _unused = get_client_ip(request)
    pending = Order.objects.filter(
        user=user, course_key=course_key, product=Product.CERTIFICATE, status=OrderStatus.PENDING,
    ).exclude(yookassa_payment_id__isnull=True)
    for order in pending:
        order = sync_order_from_yookassa(order, source_ip=client_ip)
        if order.status == OrderStatus.PAID:
            return order
    return None


@login_required
@require_http_methods(['GET', 'POST'])
def certificate_checkout(request, course_id):
    """GET: confirmation (course, price); POST: order + redirect to YooKassa."""
    if not payments_enabled():
        raise Http404('Payments are not enabled')

    try:
        course_key = CourseKey.from_string(course_id)
    except InvalidKeyError as exc:
        raise Http404 from exc
    try:
        overview = CourseOverview.get_from_id(course_key)
    except CourseOverview.DoesNotExist as exc:
        raise Http404 from exc

    if offers.active_offer(course_key) is None:
        return _error_page(request, 'certificate_unavailable')

    enrollment = CourseEnrollment.get_enrollment(request.user, course_key)
    if enrollment is None or not enrollment.is_active:
        return _error_page(request, 'certificate_not_enrolled', course_key=course_key)

    if request.method == 'POST':
        paid = _sync_pending_orders(request.user, course_key, request)
        if paid is not None:
            return redirect(reverse('robbo_payments:receipt') + f'?order_number={paid.order_number}')

    course_grade = CourseGradeFactory().read(request.user, course_key=course_key)
    state = None
    if course_grade.passed:
        state = offers.purchase_state(request.user, course_key, enrollment.mode, course_grade)
    # Not passed, below the threshold, free or already bought: the progress page says what to do
    if state is None or state.state == offers.BELOW_THRESHOLD:
        return _progress_redirect(course_key)

    offer = state.offer
    if request.method == 'GET':
        return render_to_response('robbo_payments/checkout.html', checkout_context(
            product=Product.CERTIFICATE,
            course_key=course_key,
            course_name=overview.display_name_with_default,
            price_display=format_checkout_price_display(offer.price, offer.currency),
            email=_customer_email(request.user),
            checkout_url=request.path,
            yookassa_configured=is_yookassa_configured(),
        ))

    if not is_yookassa_configured():
        return _error_page(request, 'payment_not_configured')

    order = Order.objects.create(
        user=request.user,
        course_key=course_key,
        product=Product.CERTIFICATE,
        sku=offer.sku,
        amount=offer.price,
        currency=offer.currency,
        idempotency_key=new_idempotency_key(),
    )
    description = pick(TEXTS['description']).format(course_name=overview.display_name_with_default)
    try:
        confirmation_url = create_redirect_payment(order, description, _customer_email(request.user), request)
    except (YooKassaNotConfigured, YooKassaPaymentError):
        order.delete()
        return _error_page(request, 'payment_failed')

    return redirect(confirmation_url)
