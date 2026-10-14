# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of the Robbo Open edX distribution. See NOTICE at repository root.

"""
Let browsers cache unlocked course assets (course images and thumbnails, files from
Files & Uploads) for a while.

With ``CourseAssetCacheTtlConfig.cache_ttl`` at 0 (upstream default) the contentserver sends
no ``Cache-Control``, so the catalog and the learner dashboard revalidate every course image
on each visit. Locked assets stay ``private, no-cache`` regardless of this setting.

Asset URLs are not versioned: a file replaced under the same name in Studio may stay stale
in a browser for up to the TTL, hence a short default.

Idempotent: does nothing when the current config already matches.
"""
from django.core.management.base import BaseCommand

from openedx.core.djangoapps.contentserver.models import CourseAssetCacheTtlConfig

DEFAULT_TTL = 3600


class Command(BaseCommand):
    help = 'Set the browser cache TTL for unlocked course assets (default: 1 hour).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--ttl',
            type=int,
            default=DEFAULT_TTL,
            help=f'Cache TTL in seconds; 0 disables caching headers (default: {DEFAULT_TTL}).',
        )

    def handle(self, *args, **options):
        ttl = options['ttl']
        if CourseAssetCacheTtlConfig.get_cache_ttl() == ttl:
            self.stdout.write(f'Course asset cache TTL already {ttl}s; nothing to do.')
            return
        CourseAssetCacheTtlConfig.objects.create(enabled=True, cache_ttl=ttl)
        self.stdout.write(f'Course asset cache TTL set to {ttl}s.')
