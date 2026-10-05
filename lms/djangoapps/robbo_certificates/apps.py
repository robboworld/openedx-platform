# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (certificate designs). See NOTICE at repository root.

"""Application configuration for Robbo certificate designs."""

from django.apps import AppConfig


class RobboCertificatesConfig(AppConfig):
    """Certificate designs: theme partials plus designs uploaded by platform staff in Studio."""

    name = 'lms.djangoapps.robbo_certificates'
    verbose_name = 'Robbo Certificate Designs'
    default_auto_field = 'django.db.models.AutoField'
