"""
Russian phrasing for Studio release/staff-lock attribution strings.
"""
# Modifications Copyright (C) 2026 Robbo. See NOTICE at repository root.

from django.utils.translation import gettext as _

from xmodule.course_metadata_utils import is_russian_language

from .helpers import xblock_type_display_name

_GENITIVE_LABELS = {
    'chapter': 'Раздела',
    'sequential': 'Подраздела',
    'vertical': 'Блока',
}


def xblock_release_source_label(xblock):
    """
    Return a localized label for the section/subsection that sets dates or locks.
    """
    category = getattr(xblock, 'category', None)
    if is_russian_language() and category in _GENITIVE_LABELS:
        return f'{_GENITIVE_LABELS[category]} «{xblock.display_name_with_default}»'

    return _('{section_or_subsection} "{display_name}"').format(
        section_or_subsection=xblock_type_display_name(xblock),
        display_name=xblock.display_name_with_default,
    )
