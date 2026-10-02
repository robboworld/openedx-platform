# Copyright (C) 2024-2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of the Robbo Open edX distribution. See NOTICE at repository root.

"""
Enable course image thumbnails for the /courses catalog and the learner dashboard.

With ``CourseOverviewImageConfig`` disabled (upstream default) both pages load the original
course images, some of them 1.2–1.6 MB PNGs. Thumbnails are generated as JPEG, so the source
images must not rely on transparency.

Idempotent: does nothing when the current config already matches. Upstream does not rebuild
existing thumbnails when the config changes, so image sets are recreated here.
"""
from django.core.management.base import BaseCommand

from openedx.core.djangoapps.content.course_overviews.models import (
    CourseOverview,
    CourseOverviewImageConfig,
    CourseOverviewImageSet,
)

# 2x of the ~375px catalog/dashboard card width; large is used on the course About page.
SMALL = (750, 400)
LARGE = (1500, 800)


class Command(BaseCommand):
    help = 'Enable course image thumbnails (750×400 / 1500×800) and rebuild them for all courses.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Rebuild thumbnails even if the config already matches.',
        )

    def handle(self, *args, **options):
        current = CourseOverviewImageConfig.current()
        up_to_date = current.enabled and current.small == SMALL and current.large == LARGE
        if up_to_date and not options['force']:
            self.stdout.write('Course thumbnails already enabled; nothing to do.')
            return

        if not up_to_date:
            CourseOverviewImageConfig.objects.create(
                enabled=True,
                small_width=SMALL[0],
                small_height=SMALL[1],
                large_width=LARGE[0],
                large_height=LARGE[1],
            )

        CourseOverviewImageSet.objects.all().delete()
        built = failed = 0
        for overview in CourseOverview.objects.all():
            try:
                CourseOverviewImageSet.create(overview)
            except Exception as ex:  # pylint: disable=broad-except
                failed += 1
                self.stderr.write(f'{overview.id}: {ex}')
            else:
                built += 1
        self.stdout.write(f'Course thumbnails enabled; image sets rebuilt: {built}, failed: {failed}.')
