# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (paid certificates). See NOTICE at repository root.
"""
Paid certificates: whether a learner's certificate is blocked, free, or for sale.

The rules live here; filters.py (certificate generation), the progress page certificate block
(courseware ``get_cert_data``) and the robbo_payments checkout all ask this module.
Docs: docs/paid-certificates.md in the meta repo.

The feature works only when the ``robbo_certificates.paid_certificates`` waffle switch is on
and Robbo payments are enabled: without a way to pay, nobody would get a certificate.
"""

import logging
from collections import namedtuple
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from edx_toggles.toggles import WaffleSwitch

from .models import CertificateEntitlement, CertificateOffer

log = logging.getLogger(__name__)

# .. toggle_name: robbo_certificates.paid_certificates
# .. toggle_implementation: WaffleSwitch
# .. toggle_default: False
# .. toggle_description: Sell certificates of courses with an enabled CertificateOffer (YooKassa, robbo_payments).
#   Off: every CertificateOffer is ignored and certificates are free as before.
# .. toggle_use_cases: open_edx
# .. toggle_creation_date: 2026-10-28
PAID_CERTIFICATES = WaffleSwitch('robbo_certificates.paid_certificates', __name__)

# purchase_state() results
AVAILABLE = 'available'              # passed, may buy
BELOW_THRESHOLD = 'below_threshold'  # passed the course, but below the offer's min_percent
PENDING = 'pending'                  # a payment was started a moment ago

# A started payment hides the «buy» button for this long; after that the learner may pay again
# (an abandoned YooKassa page leaves the order pending).
PENDING_ORDER_WINDOW = timedelta(minutes=30)

PurchaseState = namedtuple('PurchaseState', 'state offer percent min_percent order_number')


def feature_enabled():
    """The switch is on and there is a way to pay (Robbo payments enabled)."""
    if not PAID_CERTIFICATES.is_enabled():
        return False
    from lms.djangoapps.robbo_payments.utils import payments_enabled  # LMS only; this app is in Studio too
    return payments_enabled()


def active_offer(course_key):
    """The enabled CertificateOffer of the course, or None (also when the feature is off)."""
    if not feature_enabled():
        return None
    return CertificateOffer.objects.filter(course_key=course_key, is_enabled=True).first()


def course_min_percent(course_key):
    """The course passing grade in percent (Studio «Оценивание»), or None if unknown."""
    from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
    try:
        overview = CourseOverview.get_from_id(course_key)
    except CourseOverview.DoesNotExist:
        return None
    if overview.lowest_passing_grade is None:
        return None
    return int((Decimal(overview.lowest_passing_grade) * 100).to_integral_value())


def min_percent_error(course_key, min_percent):
    """Russian message why ``min_percent`` can't be the offer's threshold, or None (Django admin, Studio «Тип курса»)."""
    if min_percent is None:
        return None
    if not 0 <= min_percent <= 100:
        return 'Порог — от 0 до 100 %.'
    passing = course_min_percent(course_key)
    if passing is not None and min_percent < passing:
        return (
            f'Порог не может быть ниже проходного балла курса ({passing} %): '
            'платформа не выдаёт сертификат тем, кто курс не прошёл. '
            'Чтобы снизить порог, измените «Оценивание» в редакторе курса.'
        )
    return None


def grade_percent(course_grade):
    """0–100 from a CourseGrade or a 0–1 number (the generation filter declares ``grade`` as a float)."""
    value = course_grade if isinstance(course_grade, (int, float)) else getattr(course_grade, 'percent', 0)
    return int(round((value or 0) * 100))


def has_entitlement(user, course_key):
    return CertificateEntitlement.objects.filter(
        user=user, course_key=course_key, revoked_at__isnull=True,
    ).exists()


def is_free_for(offer, user, mode):
    """The certificate is included: the enrollment mode or the learner's group is in the offer's free list."""
    if mode in (offer.free_for_modes or []):
        return True
    cohort_ids = set(offer.free_for_cohorts.values_list('id', flat=True))
    if not cohort_ids:
        return False
    from openedx.core.djangoapps.course_groups.cohorts import get_cohort
    cohort = get_cohort(user, offer.course_key, assign=False)
    return cohort is not None and cohort.id in cohort_ids


def _on_allowlist(user, course_key):
    from lms.djangoapps.certificates.api import is_on_allowlist
    return is_on_allowlist(user, course_key)


def blocking_reason(user, course_key, mode, course_grade):
    """
    Why the certificate must not be created now, or None.

    Called by the certificate generation filter for every attempt (passing signal, «Запросить
    сертификат», batch generation by the course team). Learners on the certificate allowlist
    («Исключения» on the instructor dashboard) are never blocked.
    """
    offer = active_offer(course_key)
    if offer is None or _on_allowlist(user, course_key):
        return None
    if offer.min_percent is not None and grade_percent(course_grade) < offer.min_percent:
        return f'grade below the paid certificate threshold of {offer.min_percent}%'
    if is_free_for(offer, user, mode) or has_entitlement(user, course_key):
        return None
    return 'the certificate of this course is paid and the learner has not bought it'


def _recent_pending_order(user, course_key):
    from lms.djangoapps.robbo_payments.constants import OrderStatus, Product
    from lms.djangoapps.robbo_payments.models import Order
    return Order.objects.filter(
        user=user, course_key=course_key, product=Product.CERTIFICATE, status=OrderStatus.PENDING,
        created_at__gte=timezone.now() - PENDING_ORDER_WINDOW,
    ).first()


def purchase_state(user, course_key, mode, course_grade):
    """
    What the learner who passed the course sees about a paid certificate: a PurchaseState
    (AVAILABLE, BELOW_THRESHOLD, PENDING) or None when the platform's own certificate flow applies
    (no offer, allowlisted, free for the learner, already bought).
    """
    offer = active_offer(course_key)
    if offer is None or _on_allowlist(user, course_key):
        return None
    percent = grade_percent(course_grade)
    if offer.min_percent is not None and percent < offer.min_percent:
        return PurchaseState(BELOW_THRESHOLD, offer, percent, offer.min_percent, None)
    if is_free_for(offer, user, mode) or has_entitlement(user, course_key):
        return None
    pending = _recent_pending_order(user, course_key)
    if pending is not None:
        return PurchaseState(PENDING, offer, percent, offer.min_percent, pending.order_number)
    return PurchaseState(AVAILABLE, offer, percent, offer.min_percent, None)


def offer_payload(state):
    """``robbo_offer`` of the progress page certificate block (CertificateDataSerializer)."""
    from lms.djangoapps.robbo_payments.utils import format_checkout_price_display
    offer = state.offer
    payload = {
        'state': state.state,
        'price': str(offer.price),
        'currency': offer.currency,
        'price_display': format_checkout_price_display(offer.price, offer.currency),
        'percent': state.percent,
        'min_percent': state.min_percent,
        'checkout_url': reverse('robbo_payments:certificate_checkout', kwargs={'course_id': str(offer.course_key)}),
        'receipt_url': None,
    }
    if state.order_number:
        payload['receipt_url'] = (
            reverse('robbo_payments:receipt') + f'?order_number={state.order_number}'
        )
    return payload


@transaction.atomic
def grant(user, course_key, source, order_number='', granted_by=None):
    """
    Give the learner the right to the certificate (idempotent); a revoked right is restored.
    The caller starts certificate generation (after commit).
    """
    entitlement, created = CertificateEntitlement.objects.select_for_update().get_or_create(
        user=user, course_key=course_key,
        defaults={'source': source, 'order_number': order_number, 'granted_by': granted_by},
    )
    if not created and entitlement.revoked_at is not None:
        entitlement.revoked_at = None
        entitlement.source = source
        entitlement.order_number = order_number
        entitlement.granted_by = granted_by
        entitlement.save()
    log.info('Certificate entitlement for user %s in %s: %s (%s)', user.id, course_key, source,
             'new' if created else 'existing')
    return entitlement


def generate_certificate(user, course_key):
    """Ask the platform to create the certificate now that the learner has the right to it."""
    from lms.djangoapps.certificates.generation_handler import (
        CertificateGenerationNotAllowed,
        generate_certificate_task,
    )
    try:
        return generate_certificate_task(user, course_key, generation_mode='self')
    except CertificateGenerationNotAllowed:
        log.warning('Certificate for user %s in %s was not generated after purchase', user.id, course_key)
        return False
