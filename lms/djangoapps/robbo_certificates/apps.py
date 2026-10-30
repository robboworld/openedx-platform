# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (certificate designs). See NOTICE at repository root.

"""Application configuration for Robbo certificate designs and paid certificates."""

import logging

from django.apps import AppConfig
from django.conf import settings

log = logging.getLogger(__name__)

CERTIFICATE_CREATION_FILTER = 'org.openedx.learning.certificate.creation.requested.v1'


class RobboCertificatesConfig(AppConfig):
    """Certificate designs: theme partials plus designs uploaded by platform staff in Studio."""

    name = 'lms.djangoapps.robbo_certificates'
    verbose_name = 'Robbo Certificate Designs'
    default_auto_field = 'django.db.models.AutoField'

    def ready(self):
        _ensure_paid_certificate_filter()


def _ensure_paid_certificate_filter():
    """
    Keep the paid certificate step in the certificate creation pipeline even if a deployment's YAML
    sets its own OPEN_EDX_FILTERS_CONFIG: without it, paid certificates would be given away free.
    """
    step = getattr(settings, 'ROBBO_PAID_CERTIFICATE_FILTER_STEP', None)
    if not step:  # Studio: no certificate generation there
        return
    config = getattr(settings, 'OPEN_EDX_FILTERS_CONFIG', None)
    if config is None:
        config = settings.OPEN_EDX_FILTERS_CONFIG = {}
    filter_config = config.setdefault(CERTIFICATE_CREATION_FILTER, {'fail_silently': False, 'pipeline': []})
    pipeline = filter_config.setdefault('pipeline', [])
    if step not in pipeline:
        pipeline.append(step)
        log.warning('OPEN_EDX_FILTERS_CONFIG had no %s step; added', step)
