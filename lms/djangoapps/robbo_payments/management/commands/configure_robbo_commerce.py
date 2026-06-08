# Copyright (C) 2024-2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (YooKassa checkout). See NOTICE at repository root.

"""Enable Robbo YooKassa commerce alongside legacy CommerceConfiguration."""

import logging

from django.core.management import BaseCommand

from lms.djangoapps.commerce.models import CommerceConfiguration

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Enable commerce checkout URLs that point to Robbo YooKassa basket flow."""

    help = 'Enable Robbo YooKassa payments and legacy CommerceConfiguration checkout.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--disable',
            dest='disable',
            action='store_true',
            default=False,
            help='Disable commerce checkout configuration.',
        )

    def handle(self, *args, **options):
        disable = options.get('disable')

        pk_id = 1
        CommerceConfiguration.objects.update_or_create(
            id=pk_id,
            defaults={
                'id': pk_id,
                'enabled': not disable,
                'checkout_on_ecommerce_service': not disable,
                'basket_checkout_page': '/basket/add/',
            },
        )

        state = 'disabled' if disable else 'enabled'
        logger.info('Robbo commerce configuration %s (YooKassa checkout at /basket/add/).', state)
        self.stdout.write(self.style.SUCCESS(f'Robbo commerce {state}.'))
