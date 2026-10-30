# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (paid certificates). See NOTICE at repository root.

"""Tests for «Курс пройден — сертификат можно оформить за N ₽»: the passing signal and the command."""

import json
from decimal import Decimal
from io import StringIO
from unittest.mock import MagicMock, patch

from django.core import mail
from django.core.management import CommandError, call_command
from django.test import override_settings
from edx_toggles.toggles.testutils import override_waffle_flag, override_waffle_switch

from common.djangoapps.course_modes.models import CourseMode
from common.djangoapps.student.models import CourseEnrollment
from common.djangoapps.student.tests.factories import UserFactory
from lms.djangoapps.commerce.models import CommerceConfiguration
from lms.djangoapps.grades.models import PersistentCourseGrade
from lms.djangoapps.robbo_certificates import offers
from lms.djangoapps.robbo_certificates.models import CertificateEntitlement, CertificateOffer, CertificateOfferNotice
from lms.djangoapps.robbo_certificates.notifications import NOTIFICATION_TYPE
from openedx.core.djangoapps.notifications.config.waffle import ENABLE_EMAIL_NOTIFICATIONS, ENABLE_NOTIFICATIONS
from openedx.core.djangoapps.notifications.models import Notification
from openedx.core.djangoapps.notifications.robbo_account import ACCOUNT_KEY
from openedx.core.djangoapps.signals.signals import COURSE_GRADE_NOW_PASSED
from openedx.core.djangoapps.user_api.models import UserPreference
from openedx.core.djangolib.testing.utils import skip_unless_lms
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory

GRADE_READ = 'lms.djangoapps.grades.course_grade_factory.CourseGradeFactory.read'


def _grade(percent, passed=True):
    return MagicMock(percent=percent, passed=passed)


@skip_unless_lms
@override_settings(ROBBO_PAYMENTS_ENABLED=True)
@override_waffle_switch(offers.PAID_CERTIFICATES, active=True)
@override_waffle_flag(ENABLE_NOTIFICATIONS, active=True)
@override_waffle_flag(ENABLE_EMAIL_NOTIFICATIONS, active=True)
@patch('lms.djangoapps.robbo_certificates.offers._on_allowlist', return_value=False)
class OfferNotificationTests(ModuleStoreTestCase):
    """One notification (bell + email) per learner and course, only while the certificate is for sale."""

    def setUp(self):
        super().setUp()
        CommerceConfiguration.objects.update_or_create(
            id=1, defaults={'enabled': True, 'checkout_on_ecommerce_service': True},
        )
        self.course = CourseFactory.create(display_name='Роботы')
        self.course_key = self.course.id
        self.user = UserFactory.create()
        CourseEnrollment.enroll(self.user, self.course_key, CourseMode.HONOR)
        self.offer = CertificateOffer.objects.create(course_key=self.course_key, price=Decimal('990.00'))

    def _pass(self, user=None, grade=None):
        with patch(GRADE_READ, return_value=grade or _grade(0.9)):
            with self.captureOnCommitCallbacks(execute=True):
                COURSE_GRADE_NOW_PASSED.send(sender=None, user=user or self.user, course_id=self.course_key)

    def _notifications(self, user=None):
        return Notification.objects.filter(user=user or self.user, notification_type=NOTIFICATION_TYPE)

    def test_first_pass_sends_bell_and_email_once(self, _allowlist):
        self._pass()
        notification = self._notifications().get()
        assert notification.web and notification.email
        assert notification.content_context['price_display'] == '990 ₽'
        assert notification.content_url.endswith(f'/courses/{self.course_key}/progress')
        assert len(mail.outbox) == 1
        assert 'Роботы' in mail.outbox[0].subject
        assert CertificateOfferNotice.objects.get(user=self.user).source == CertificateOfferNotice.SOURCE_PASSED
        # Every later grade update of a passing learner sends the signal again
        self._pass()
        self._pass()
        assert self._notifications().count() == 1
        assert len(mail.outbox) == 1

    def test_not_sent_again_after_old_notifications_are_deleted(self, _allowlist):
        self._pass()
        Notification.objects.all().delete()
        self._pass()
        assert not self._notifications().exists()

    def test_not_for_sale_sends_nothing(self, _allowlist):
        verified = UserFactory.create()
        CourseEnrollment.enroll(verified, self.course_key, CourseMode.VERIFIED)
        bought = UserFactory.create()
        CourseEnrollment.enroll(bought, self.course_key, CourseMode.HONOR)
        offers.grant(bought, self.course_key, CertificateEntitlement.SOURCE_PAID, 'ROBBO-1')
        self._pass(verified)
        self._pass(bought)
        self.offer.min_percent = 95
        self.offer.save()
        self._pass()  # below the threshold
        assert not Notification.objects.filter(notification_type=NOTIFICATION_TYPE).exists()
        assert not CertificateOfferNotice.objects.exists()
        # Reaches the threshold later: now it is for sale
        self._pass(grade=_grade(0.97))
        assert self._notifications().count() == 1

    def test_feature_off_does_nothing(self, _allowlist):
        with patch('lms.djangoapps.robbo_certificates.notifications.notify_certificate_offer.delay') as delay:
            with override_waffle_switch(offers.PAID_CERTIFICATES, active=False):
                self._pass()
            self.offer.is_enabled = False
            self.offer.save()
            self._pass()
        assert not delay.called
        assert not CertificateOfferNotice.objects.exists()

    def test_all_notifications_off_sends_nothing(self, _allowlist):
        # «Отключить все уведомления» stored every known type off; the new type has no entry yet
        UserPreference.objects.create(user=self.user, key=ACCOUNT_KEY, value=json.dumps({
            'learning.learner_certificate_issued': {'web': False, 'email': False, 'email_cadence': 'Daily'},
        }))
        self._pass()
        assert not self._notifications().exists()
        assert not CertificateOfferNotice.objects.exists()

    def test_site_notifications_off_keeps_it_for_later(self, _allowlist):
        with override_waffle_flag(ENABLE_NOTIFICATIONS, active=False):
            self._pass()
        assert not CertificateOfferNotice.objects.exists()
        self._pass()
        assert self._notifications().count() == 1

    def _persist(self, user, passed=True):
        PersistentCourseGrade.update_or_create(
            user_id=user.id, course_id=self.course_key, passed=passed, percent_grade=0.9 if passed else 0.2,
            letter_grade='Pass' if passed else '', grading_policy_hash='hash',
        )

    def test_command_for_learners_who_passed_before(self, _allowlist):
        failing = UserFactory.create()
        CourseEnrollment.enroll(failing, self.course_key, CourseMode.HONOR)
        verified = UserFactory.create()
        CourseEnrollment.enroll(verified, self.course_key, CourseMode.VERIFIED)
        with override_waffle_switch(offers.PAID_CERTIFICATES, active=False):  # passed before the sale
            self._persist(self.user)
            self._persist(verified)
            self._persist(failing, passed=False)

        out = StringIO()
        with patch(GRADE_READ, return_value=_grade(0.9)):
            call_command('robbo_certificate_offer_notify', '--course', str(self.course_key), '--dry-run', stdout=out)
        assert '2 learners passing the course (dry run)' in out.getvalue()
        assert 'would be sent: 1' in out.getvalue()
        assert not Notification.objects.exists() and not CertificateOfferNotice.objects.exists()

        out = StringIO()
        with patch(GRADE_READ, return_value=_grade(0.9)):
            call_command('robbo_certificate_offer_notify', '--course', str(self.course_key), stdout=out)
            call_command('robbo_certificate_offer_notify', '--course', str(self.course_key), stdout=out)
        assert self._notifications().count() == 1
        assert len(mail.outbox) == 1
        assert CertificateOfferNotice.objects.get().source == CertificateOfferNotice.SOURCE_COMMAND
        assert 'already notified: 1' in out.getvalue()
        # The passing signal afterwards sends nothing either
        self._pass()
        assert self._notifications().count() == 1

    def test_command_refuses_course_without_sale(self, _allowlist):
        self.offer.is_enabled = False
        self.offer.save()
        with self.assertRaises(CommandError):
            call_command('robbo_certificate_offer_notify', '--course', str(self.course_key))
