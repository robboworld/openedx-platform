# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (human-readable errors). See NOTICE at repository root.
"""Application configuration of the error journal."""

from django.apps import AppConfig
from django.core.signals import got_request_exception
from django.db.models.signals import post_migrate

SUPPORT_GROUP = 'Поддержка'


def ensure_support_group(sender, **kwargs):  # pylint: disable=unused-argument
    """The «Поддержка» group: may open the journal's support page, nothing else."""
    from django.contrib.auth.models import Group, Permission  # pylint: disable=import-outside-toplevel

    permission = Permission.objects.filter(
        content_type__app_label='robbo_errors', codename='view_errorincident',
    ).first()
    if permission is not None:
        Group.objects.get_or_create(name=SUPPORT_GROUP)[0].permissions.add(permission)


class RobboErrorsConfig(AppConfig):
    """Human-readable errors: catalog of codes, error journal, incident numbers."""

    name = 'lms.djangoapps.robbo_errors'
    label = 'robbo_errors'
    verbose_name = 'Robbo Error Journal'
    default_auto_field = 'django.db.models.AutoField'

    def ready(self):
        from .middleware import journal_uncaught_exception  # pylint: disable=import-outside-toplevel

        got_request_exception.connect(journal_uncaught_exception, dispatch_uid='robbo_errors_uncaught')
        post_migrate.connect(ensure_support_group, sender=self, dispatch_uid='robbo_errors_support_group')
