# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (paid certificates). See NOTICE at repository root.
"""
openedx-filters step that keeps paid certificates from being created before they are bought.

Wired in ``OPEN_EDX_FILTERS_CONFIG`` (lms/envs/common.py) on
``org.openedx.learning.certificate.creation.requested.v1``, which the platform runs before every
certificate generation task. The rules are in offers.blocking_reason.
"""

import logging

from openedx_filters import PipelineStep
from openedx_filters.learning.filters import CertificateCreationRequested

from . import offers

log = logging.getLogger(__name__)


class RequirePaidCertificate(PipelineStep):
    """Stop certificate creation for a paid certificate the learner has not bought."""

    def run_filter(self, user, course_key, mode, status, grade, generation_mode):  # pylint: disable=arguments-differ
        if not offers.PAID_CERTIFICATES.is_enabled():
            return {}
        try:
            reason = offers.blocking_reason(user, course_key, mode, grade)
        except Exception:  # pylint: disable=broad-except
            # Fail closed: a broken check must not give a paid certificate away. The learner can request
            # the certificate again once it is fixed.
            log.exception('Paid certificate check failed for user %s in %s', getattr(user, 'id', None), course_key)
            reason = 'the paid certificate check failed'
        if reason:
            raise CertificateCreationRequested.PreventCertificateCreation(reason)
        return {}
