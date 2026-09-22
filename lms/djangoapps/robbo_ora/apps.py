# Copyright (C) 2024-2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only

from django.apps import AppConfig


class RobboOraConfig(AppConfig):
    name = 'lms.djangoapps.robbo_ora'
    verbose_name = 'Robbo ORA'

    def ready(self):
        from cms.djangoapps.contentstore.robbo_ora_i18n import (
            patch_ora_xblock_i18n,
            patch_robbo_ora_django_catalog,
        )
        from cms.djangoapps.contentstore.robbo_ora_limits import (
            patch_ora_lms_student_view,
            patch_ora_runtime_limits,
        )

        patch_ora_runtime_limits()
        patch_ora_lms_student_view()
        patch_ora_xblock_i18n()
        patch_robbo_ora_django_catalog()
