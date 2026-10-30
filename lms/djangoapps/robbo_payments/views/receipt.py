# Copyright (C) 2024-2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (YooKassa checkout). See NOTICE at repository root.

"""Order receipt page after YooKassa redirect: the state of the order and what to do next (pages.py)."""

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.urls import reverse
from django.utils.http import urlencode
from django.views.decorators.http import require_GET
from ipware import get_client_ip

from common.djangoapps.course_modes.models import CourseMode
from common.djangoapps.edxmako.shortcuts import render_to_response
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview

from ..constants import OrderStatus, Product
from ..models import Order
from ..pages import receipt_context
from ..services.sync import sync_order_from_yookassa
from ..utils import payments_enabled


def _retry_url(order):
    """Where «Попробовать ещё раз» leads: the checkout of the same product, if it is still sold."""
    if order.product == Product.CERTIFICATE:
        return reverse('robbo_payments:certificate_checkout', kwargs={'course_id': str(order.course_key)})
    mode = CourseMode.verified_mode_for_course(order.course_key)
    if mode is None or not mode.sku:
        return None
    query = urlencode({'sku': mode.sku, 'course_run_key': str(order.course_key)})
    return f'{reverse("robbo_payments:basket_add")}?{query}'


def _course_name(course_key):
    try:
        return CourseOverview.get_from_id(course_key).display_name_with_default
    except CourseOverview.DoesNotExist:
        return str(course_key)


@login_required
@require_GET
def receipt(request):
    """Show payment receipt for the authenticated user."""
    if not payments_enabled():
        raise Http404

    order_number = request.GET.get('order_number')
    if not order_number:
        raise Http404

    try:
        order = Order.objects.get(order_number=order_number, user=request.user)
    except Order.DoesNotExist as exc:
        raise Http404 from exc

    if order.status == OrderStatus.PENDING:
        client_ip, _unused = get_client_ip(request)
        order = sync_order_from_yookassa(order, source_ip=client_ip)

    retry_url = _retry_url(order) if order.status in (OrderStatus.CANCELED, OrderStatus.FAILED) else None
    return render_to_response(
        'robbo_payments/receipt.html',
        receipt_context(order, _course_name(order.course_key), retry_url),
    )
