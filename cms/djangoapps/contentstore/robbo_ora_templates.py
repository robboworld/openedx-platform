# Copyright (C) 2024-2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only

"""Robbo ORA: reorder Studio creation templates (swap 1st and 3rd)."""

from django.utils.translation import gettext_lazy as _

# Upstream order: peer, self, staff, self-to-peer, self-to-staff.
# Robbo: staff first, self second, peer third (was first).
ROBBO_ORA_TEMPLATE_ORDER = [
    'staff-assessment',
    'self-assessment',
    'peer-assessment',
    'self-to-peer',
    'self-to-staff',
]

ROBBO_ORA_TEMPLATE_DISPLAY_NAMES = {
    'peer-assessment': _('Peer Assessment Only'),
    'self-assessment': _('Self Assessment Only'),
    'staff-assessment': _('Staff Assessment Only'),
    'self-to-peer': _('Self Assessment to Peer Assessment'),
    'self-to-staff': _('Self Assessment to Staff Assessment'),
}


def patch_ora_creation_templates():
    """Reorder ORA boilerplates; hide staff duplicate (default entry in component.py)."""
    from openassessment.xblock.openassesment_template_mixin import OpenAssessmentTemplatesMixin

    if getattr(OpenAssessmentTemplatesMixin, '_robbo_templates_patched', False):
        return

    original_templates = OpenAssessmentTemplatesMixin.templates

    @classmethod
    def templates(cls):
        by_id = {template['template_id']: template for template in original_templates()}
        ordered = []
        for template_id in ROBBO_ORA_TEMPLATE_ORDER:
            if template_id not in by_id:
                continue
            ordered.append({
                'template_id': template_id,
                'metadata': {
                    'display_name': ROBBO_ORA_TEMPLATE_DISPLAY_NAMES[template_id],
                },
            })
        return ordered

    @classmethod
    def filter_templates(cls, template, courselike):
        # Staff is prepended as the default blank ORA in component.py.
        return template['template_id'] != 'staff-assessment'

    OpenAssessmentTemplatesMixin.templates = templates
    OpenAssessmentTemplatesMixin.filter_templates = filter_templates
    OpenAssessmentTemplatesMixin._robbo_templates_patched = True
