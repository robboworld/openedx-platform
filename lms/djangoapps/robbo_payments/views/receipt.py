# Copyright (C) 2024-2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (YooKassa checkout). See NOTICE at repository root.

"""Order receipt page after YooKassa redirect."""

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET
from ipware import get_client_ip

from common.djangoapps.edxmako.shortcuts import render_to_response
from openedx.features.course_experience.url_helpers import get_learning_mfe_home_url

from ..constants import OrderStatus
from ..models import Order
from ..services.sync import sync_order_from_yookassa
from ..utils import payments_enabled


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

    course_outline_url = get_learning_mfe_home_url(order.course_key, 'home')
    status_messages = {
        OrderStatus.PAID: _('Оплата прошла успешно. Полный доступ к курсу активирован.'),
        OrderStatus.PENDING: _('Платёж ещё обрабатывается. Обновите страницу через минуту.'),
        OrderStatus.CANCELED: _('Оплата отменена.'),
        OrderStatus.FAILED: _('Оплата не выполнена.'),
    }

    return render_to_response('robbo_payments/receipt.html', {
        'order': order,
        'status_message': status_messages.get(order.status, ''),
        'course_outline_url': course_outline_url,
        'is_paid': order.status == OrderStatus.PAID,
    })
