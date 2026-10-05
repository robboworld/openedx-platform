# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (certificate designs). See NOTICE at repository root.
"""
Field schema of uploaded certificate designs.

Every field is a dict; positions are percentages of the A4 landscape sheet so the same
layout works on the certificate page, in print and in the Studio preview:

    {"type": "recipient", "x": 50, "y": 40, "width": 70, "align": "center",
     "font": "proxima", "font_size": 28, "bold": true, "color": "#383838",
     "uppercase": false, "lines": 1, "prefix": "", "suffix": "", "text": ""}

``x`` is the left edge / centre / right edge for align left / center / right; ``y`` is the top edge.
Text longer than ``lines`` lines shrinks until it fits ``width``. For ``signature`` only
x, y, width and align matter (the image keeps its aspect ratio). ``hours`` shows the course
volume from Studio (``format_hours``), e.g. prefix "в объеме " + "72 часов".
"""

import re

FIELD_TYPES = ('recipient', 'course', 'date', 'hours', 'signatory_name', 'signatory_title', 'signature', 'text')
FONTS = ('proxima', 'sans', 'serif')
ALIGNS = ('left', 'center', 'right')
MAX_FIELDS = 20

_COLOR_RE = re.compile(r'^#[0-9a-fA-F]{6}$')
_NUMBERS = {
    # name: (min, max, default)
    'x': (0, 100, 50),
    'y': (0, 100, 50),
    'width': (1, 100, 60),
    'font_size': (4, 120, 18),
    'lines': (1, 4, 1),
}
_STRINGS = {'prefix': 100, 'suffix': 100, 'text': 500}

DEFAULT_FIELDS = [
    {'type': 'recipient', 'x': 50, 'y': 42, 'width': 70, 'font_size': 30, 'bold': True},
    {'type': 'course', 'x': 50, 'y': 55, 'width': 70, 'font_size': 18, 'lines': 2, 'prefix': '«', 'suffix': '»'},
    {'type': 'date', 'x': 92, 'y': 88, 'width': 30, 'font_size': 11, 'align': 'right', 'prefix': 'Выдан: '},
]


class FieldsValidationError(ValueError):
    """Raised with a user-facing (Russian) message."""


def _number(field, name, index):
    low, high, default = _NUMBERS[name]
    value = field.get(name, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FieldsValidationError(f'Поле {index}: значение «{name}» должно быть числом.')
    if not low <= value <= high:
        raise FieldsValidationError(f'Поле {index}: значение «{name}» должно быть от {low} до {high}.')
    return int(value) if name == 'lines' else round(float(value), 2)


def clean_field(field, index=1):
    if not isinstance(field, dict):
        raise FieldsValidationError(f'Поле {index}: неверный формат.')
    field_type = field.get('type')
    if field_type not in FIELD_TYPES:
        raise FieldsValidationError(f'Поле {index}: неизвестный тип «{field_type}».')

    cleaned = {'type': field_type}
    for name in _NUMBERS:
        cleaned[name] = _number(field, name, index)
    for name, limit in _STRINGS.items():
        value = field.get(name, '')
        if not isinstance(value, str) or len(value) > limit:
            raise FieldsValidationError(f'Поле {index}: текст «{name}» длиннее {limit} символов.')
        cleaned[name] = value

    cleaned['font'] = field.get('font', 'proxima')
    cleaned['align'] = field.get('align', 'center')
    cleaned['color'] = field.get('color', '#383838')
    if cleaned['font'] not in FONTS:
        raise FieldsValidationError(f'Поле {index}: неизвестный шрифт.')
    if cleaned['align'] not in ALIGNS:
        raise FieldsValidationError(f'Поле {index}: неизвестное выравнивание.')
    if not _COLOR_RE.match(str(cleaned['color'])):
        raise FieldsValidationError(f'Поле {index}: цвет должен быть в формате #RRGGBB.')
    cleaned['bold'] = bool(field.get('bold', False))
    cleaned['uppercase'] = bool(field.get('uppercase', False))
    if field_type == 'text' and not cleaned['text'].strip():
        raise FieldsValidationError(f'Поле {index}: введите текст.')
    return cleaned


def validate_fields(fields):
    """Return a cleaned copy of ``fields`` or raise FieldsValidationError."""
    if not isinstance(fields, list):
        raise FieldsValidationError('Список полей имеет неверный формат.')
    if len(fields) > MAX_FIELDS:
        raise FieldsValidationError(f'Не больше {MAX_FIELDS} полей.')
    return [clean_field(field, index) for index, field in enumerate(fields, start=1)]


def default_fields():
    return validate_fields(DEFAULT_FIELDS)


COURSE_HOURS_KEY = 'robbo_course_hours'
MAX_COURSE_HOURS = 10000


def parse_hours(value):
    """Course volume in hours from Advanced Settings (stored as a string), or None."""
    try:
        hours = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return hours if 0 < hours <= MAX_COURSE_HOURS else None


def format_hours(value):
    """'72 часов', '21 часа' — genitive after «в объеме»; '' when the course has no volume."""
    hours = parse_hours(value)
    if hours is None:
        return ''
    noun = 'часа' if hours % 10 == 1 and hours % 100 != 11 else 'часов'
    return f'{hours} {noun}'
