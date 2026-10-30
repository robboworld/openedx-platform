# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (paid certificates). See NOTICE at repository root.
"""
Paid certificates: send «Курс пройден — сертификат можно оформить за N ₽» to learners who passed
the course before its certificate went on sale (new passes get it from the grade signal).

    ./manage.py lms robbo_certificate_offer_notify --course course-v1:ORG+NUM+RUN --dry-run
    ./manage.py lms robbo_certificate_offer_notify --course course-v1:ORG+NUM+RUN

Each learner gets it once per course, however many times this runs (notifications.py).
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey

from lms.djangoapps.grades.models import PersistentCourseGrade
from lms.djangoapps.robbo_certificates import offers
from lms.djangoapps.robbo_certificates.models import CertificateOfferNotice
from lms.djangoapps.robbo_certificates.notifications import (
    ALL_OFF,
    ALREADY_SENT,
    NOT_FOR_SALE,
    SENT,
    SITE_OFF,
    send_offer_notification,
)

User = get_user_model()

LABELS = (
    (SENT, 'sent', 'would be sent'),
    (ALREADY_SENT, 'already notified', 'already notified'),
    (NOT_FOR_SALE, 'not for sale to them (free, bought, below the threshold, paying now, not enrolled)', None),
    (ALL_OFF, 'all notifications turned off', None),
    (SITE_OFF, 'notifications are off for the course (waffle flag notifications.enable_notifications)', None),
)


class Command(BaseCommand):
    help = 'Robbo: tell learners who already passed a course that its certificate can be bought.'

    def add_arguments(self, parser):
        parser.add_argument('--course', required=True, help='Course run key, course-v1:ORG+NUM+RUN')
        parser.add_argument('--dry-run', action='store_true', help='Count only: store and send nothing.')

    def handle(self, *args, **options):
        try:
            course_key = CourseKey.from_string(options['course'])
        except InvalidKeyError as error:
            raise CommandError(f'Not a course key: {options["course"]}') from error
        if offers.active_offer(course_key) is None:
            raise CommandError(
                f'The certificate of {course_key} is not on sale: no enabled CertificateOffer, '
                'the robbo_certificates.paid_certificates switch is off or payments are off.'
            )
        dry_run = options['dry_run']
        # Passing now: the platform stores a letter grade only while the course is passed.
        user_ids = (
            PersistentCourseGrade.objects.filter(course_id=course_key).exclude(letter_grade='')
            .values_list('user_id', flat=True)
        )
        totals = dict.fromkeys((key for key, _, _ in LABELS), 0)
        for user in User.objects.filter(id__in=list(user_ids), is_active=True).iterator():
            result = send_offer_notification(user, course_key, CertificateOfferNotice.SOURCE_COMMAND, dry_run=dry_run)
            totals[result] += 1
        self.stdout.write(f'{course_key}: {sum(totals.values())} learners passing the course'
                          + (' (dry run)' if dry_run else ''))
        for key, label, dry_label in LABELS:
            self.stdout.write(f'  {(dry_label if dry_run and dry_label else label)}: {totals[key]}')
