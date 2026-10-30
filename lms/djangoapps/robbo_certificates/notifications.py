# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (paid certificates). See NOTICE at repository root.
"""
Paid certificates: «Курс … пройден — сертификат можно оформить за N ₽» in the bell and by email,
once per learner and course (CertificateOfferNotice). Docs: docs/paid-certificates.md in the meta repo.

Sent when the learner passes the course (COURSE_GRADE_NOW_PASSED, next to the platform's own receiver
in certificates/signals.py) and by ``./manage.py lms robbo_certificate_offer_notify`` for learners who
passed before the sale was turned on. Only in the AVAILABLE state of offers.purchase_state: not to
learners below the offer's threshold, with a free or bought certificate, or with a payment going on.

The notification goes through the ROBBO notification system (notifications/robbo_events.py): the
learner's settings decide the site and email channels, «Отключить все уведомления» stops it too.
"""

import logging

from celery import shared_task
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from edx_django_utils.monitoring import set_code_owner_attribute
from opaque_keys.edx.keys import CourseKey

from . import offers
from .models import CertificateOfferNotice

log = logging.getLogger(__name__)
User = get_user_model()

NOTIFICATION_APP = 'learning'
NOTIFICATION_TYPE = 'learner_certificate_offer'

# send_offer_notification() results
SENT = 'sent'
ALREADY_SENT = 'already_sent'
NOT_FOR_SALE = 'not_for_sale'      # not passed, below the threshold, free, bought, payment going on
ALL_OFF = 'notifications_off'      # the learner turned every notification off
SITE_OFF = 'site_notifications_off'  # notifications are off for the course (waffle flag): try again later


def already_notified(user, course_key):
    return CertificateOfferNotice.objects.filter(user=user, course_key=course_key).exists()


def offer_state(user, course_key):
    """offers.purchase_state of an enrolled learner who passes the course now, or None."""
    from common.djangoapps.student.models import CourseEnrollment
    from lms.djangoapps.grades.api import CourseGradeFactory
    mode, is_active = CourseEnrollment.enrollment_mode_for_user(user, course_key)
    if not is_active:
        return None
    # read() takes the stored grade and never recalculates (that would send the passing signal again).
    grade = CourseGradeFactory().read(user, course_key=course_key)
    if grade is None or not grade.passed:
        return None
    return offers.purchase_state(user, course_key, mode, grade)


def send_offer_notification(user, course_key, source, dry_run=False):
    """
    Tell the learner the certificate can be bought, unless already told. Returns SENT, ALREADY_SENT,
    NOT_FOR_SALE, ALL_OFF or SITE_OFF; with ``dry_run`` nothing is stored or sent.
    """
    from openedx.core.djangoapps.notifications.config.waffle import ENABLE_NOTIFICATIONS
    from openedx.core.djangoapps.notifications.robbo_account import all_off
    from openedx.core.djangoapps.notifications.robbo_events import lms_url, notify
    from lms.djangoapps.robbo_payments.utils import format_checkout_price_display

    if already_notified(user, course_key):
        return ALREADY_SENT
    state = offer_state(user, course_key)
    if state is None or state.state != offers.AVAILABLE:
        return NOT_FOR_SALE
    if all_off(user):
        return ALL_OFF
    if not ENABLE_NOTIFICATIONS.is_enabled(course_key):  # nothing would be created: don't mark it sent
        return SITE_OFF
    if dry_run:
        return SENT
    try:
        with transaction.atomic():
            CertificateOfferNotice.objects.create(user=user, course_key=course_key, source=source)
    except IntegrityError:  # the passing signal and the command at the same moment
        return ALREADY_SENT
    price = format_checkout_price_display(state.offer.price, state.offer.currency)
    notify([user.id], course_key, NOTIFICATION_APP, NOTIFICATION_TYPE, {'price_display': price},
           lms_url(f'/courses/{course_key}/progress'))
    log.info('Paid certificate notification for user %s in %s (%s)', user.id, course_key, source)
    return SENT


@shared_task(ignore_result=True)
@set_code_owner_attribute
def notify_certificate_offer(user_id, course_id):
    user = User.objects.filter(id=user_id, is_active=True).first()
    if user is not None:
        send_offer_notification(user, CourseKey.from_string(course_id), CertificateOfferNotice.SOURCE_PASSED)


def on_course_grade_passed(sender, user, course_id, **kwargs):  # pylint: disable=unused-argument
    """
    COURSE_GRADE_NOW_PASSED. The platform sends it on every grade update of a passing learner, so the
    cheap checks come first; the rest runs in a task after the grade is saved.
    """
    try:
        if offers.active_offer(course_id) is None or already_notified(user, course_id):
            return
    except Exception:  # pylint: disable=broad-except
        log.exception('Paid certificate notification check failed for user %s in %s', user.id, course_id)
        return
    user_id, course = user.id, str(course_id)
    transaction.on_commit(lambda: notify_certificate_offer.delay(user_id, course))
