"""
Robbo: time-based notifications (robbo_scheduled.py). Run by cron, e.g. daily at 09:00 Moscow time:

    ./manage.py lms robbo_notifications                 # every check; the weekly report on Mondays
    ./manage.py lms robbo_notifications --only deadline,overdue
    ./manage.py lms robbo_notifications --weekly        # the weekly report today as well
    ./manage.py lms robbo_notifications --course course-v1:ORG+NUM+RUN

Running it again the same day sends nothing twice.

Copyright (C) 2026 Robbo <https://robbo.ru>
SPDX-License-Identifier: AGPL-3.0-only
Part of the Robbo Open edX distribution. See NOTICE at repository root.
"""
from django.core.management.base import BaseCommand, CommandError

from openedx.core.djangoapps.notifications.robbo_scheduled import CHECKS, run


class Command(BaseCommand):
    help = 'Robbo: send time-based notifications (deadlines, new sections, overdue reviews, weekly report).'

    def add_arguments(self, parser):
        parser.add_argument('--only', default='', help=f'Comma-separated checks: {", ".join(CHECKS)}')
        parser.add_argument('--weekly', action='store_true', help='Send the weekly report today too.')
        parser.add_argument('--course', action='append', default=[], help='Limit to this course (repeatable).')

    def handle(self, *args, **options):
        only = [name.strip() for name in options['only'].split(',') if name.strip()]
        unknown = set(only) - set(CHECKS)
        if unknown:
            raise CommandError(f'Unknown checks: {", ".join(sorted(unknown))}')
        totals = run(only=only or None, weekly=True if options['weekly'] else None, course_ids=options['course'] or None)
        for name, count in totals.items():
            self.stdout.write(f'{name}: {count}')
