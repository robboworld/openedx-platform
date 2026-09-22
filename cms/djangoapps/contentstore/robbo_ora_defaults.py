"""
Russian defaults for Open Response Assessment (edx-ora2) in Robbo Studio.
"""
# Modifications Copyright (C) 2026 Robbo. See NOTICE at repository root.

import copy

from xmodule.course_metadata_utils import is_russian_language

ROBBO_ORA_DEFAULT_TITLE = "Задание с развёрнутым ответом"

ROBBO_ORA_DEFAULT_PROMPT = """
Как приготовить блины

Опишите по шагам, как вы готовите блины дома:
- какие ингредиенты нужны для теста;
- как замесить тесто до нужной консистенции;
- как разогреть сковороду и налить первую порцию;
- как понять, что блин готов с одной стороны, и когда его переворачивать.

Это учебный пример. Ответ не засчитывается в оценку курса и нужен только
для ознакомления с форматом задания с развёрнутым ответом.
""".strip()

ROBBO_ORA_DEFAULT_RUBRIC_FEEDBACK_PROMPT = """
(Необязательно) Что в этом ответе показалось вам удачным? Что можно улучшить?
""".strip()

ROBBO_ORA_DEFAULT_RUBRIC_FEEDBACK_TEXT = """
Мне кажется, этот ответ...
""".strip()

ROBBO_ORA_DEFAULT_RUBRIC_CRITERIA = [
    {
        'name': 'Ideas',
        'label': 'Идеи',
        'prompt': 'Определите, есть ли единая тема или основная мысль.',
        'order_num': 0,
        'feedback': 'optional',
        'options': [
            {
                'order_num': 0,
                'points': 0,
                'name': 'Poor',
                'label': 'Слабо',
                'explanation': (
                    'Основная мысль трудноуловима. Ответ слишком короткий или повторяется, '
                    'не удаётся удержать фокус.'
                ),
            },
            {
                'order_num': 1,
                'points': 3,
                'name': 'Fair',
                'label': 'Удовлетворительно',
                'explanation': (
                    'Есть общая тема или основная мысль, но возможны небольшие отступления. '
                    'В целом удерживается фокус на задании.'
                ),
            },
            {
                'order_num': 2,
                'points': 5,
                'name': 'Good',
                'label': 'Хорошо',
                'explanation': (
                    'Единая тема или основная мысль без лишних отступлений. '
                    'Полностью сфокусировано на задании.'
                ),
            },
        ],
    },
    {
        'name': 'Content',
        'label': 'Содержание',
        'prompt': 'Оцените содержательную часть ответа.',
        'order_num': 1,
        'options': [
            {
                'order_num': 0,
                'points': 0,
                'name': 'Poor',
                'label': 'Слабо',
                'explanation': (
                    'Почти нет информации, деталей нет или они не по теме. '
                    'Тема раскрыта слабо или не раскрыта.'
                ),
            },
            {
                'order_num': 1,
                'points': 1,
                'name': 'Fair',
                'label': 'Удовлетворительно',
                'explanation': (
                    'Мало информации и деталей. Раскрыта только одна-две стороны темы.'
                ),
            },
            {
                'order_num': 2,
                'points': 3,
                'name': 'Good',
                'label': 'Хорошо',
                'explanation': (
                    'Достаточно информации и деталей (возможно, без полной проработки). '
                    'Раскрыты некоторые стороны темы.'
                ),
            },
            {
                'order_num': 3,
                'points': 5,
                'name': 'Excellent',
                'label': 'Отлично',
                'explanation': (
                    'Глубокая проработка темы с убедительными деталями. '
                    'Раскрыты все важные стороны темы.'
                ),
            },
        ],
    },
]

ROBBO_ORA_NECESSITY_OPTIONS_RU = {
    'required': 'Обязательно',
    'optional': 'Необязательно',
    '': 'Нет',
}


def localized_ora_prompts():
    """Return ORA prompts list for the Russian locale."""
    return [{'description': ROBBO_ORA_DEFAULT_PROMPT}]


def localized_ora_rubric_criteria():
    """Return a deep copy of the Robbo Russian default rubric."""
    return copy.deepcopy(ROBBO_ORA_DEFAULT_RUBRIC_CRITERIA)


def localized_necessity_options():
    """Return necessity dropdown labels for the Studio settings editor."""
    if is_russian_language():
        return dict(ROBBO_ORA_NECESSITY_OPTIONS_RU)
    from openassessment.xblock.studio_mixin import StudioMixin
    return StudioMixin.NECESSITY_OPTIONS


def apply_russian_ora_defaults(block):
    """
    Replace upstream English sample content on newly created ORA blocks.
    """
    if not is_russian_language():
        return block
    if getattr(block, 'category', None) != 'openassessment':
        return block

    block.prompts = localized_ora_prompts()
    block.title = ROBBO_ORA_DEFAULT_TITLE
    block.display_name = ROBBO_ORA_DEFAULT_TITLE
    block.rubric_criteria = localized_ora_rubric_criteria()
    block.rubric_feedback_prompt = ROBBO_ORA_DEFAULT_RUBRIC_FEEDBACK_PROMPT
    block.rubric_feedback_default_text = ROBBO_ORA_DEFAULT_RUBRIC_FEEDBACK_TEXT
    if hasattr(block, 'max_files_count'):
        block.max_files_count = 1
    return block


def is_censorship_sample_prompt(prompts):
    """Detect the upstream edx-ora2 default prompt about library censorship."""
    if not prompts:
        return False
    text = ' '.join(
        (prompt.get('description') or '') for prompt in prompts
    ).lower()
    return 'censorship in the libraries' in text


def is_upstream_default_rubric(criteria):
    """Detect the upstream edx-ora2 sample rubric (Ideas + Content)."""
    if not criteria or len(criteria) != 2:
        return False
    names = {criterion.get('name') for criterion in criteria}
    labels = {criterion.get('label') for criterion in criteria}
    return names == {'Ideas', 'Content'} or labels == {'Ideas', 'Content'}


def should_replace_ora_prompt(prompts):
    """Return True when the ORA prompt should use the Robbo Russian default."""
    if not prompts:
        return True
    text = ' '.join((prompt.get('description') or '') for prompt in prompts)
    lowered = text.lower()
    if is_censorship_sample_prompt(prompts):
        return True
    if 'учебный пример' in lowered and ('плов' in lowered or 'блин' in lowered):
        return True
    return False


def should_replace_ora_title(title):
    """Return True when the ORA title should use the Robbo Russian default."""
    return not title or title.strip() in {'Open Response Assessment', ROBBO_ORA_DEFAULT_TITLE}


def should_replace_ora_rubric(criteria):
    """Return True when the ORA rubric should use the Robbo Russian default."""
    return is_upstream_default_rubric(criteria)


def apply_russian_ora_content(block):
    """Apply Russian defaults to an existing block when upstream samples are detected."""
    if not is_russian_language() or getattr(block, 'category', None) != 'openassessment':
        return block

    if should_replace_ora_prompt(block.prompts):
        block.prompts = localized_ora_prompts()
    if should_replace_ora_title(block.title):
        block.title = ROBBO_ORA_DEFAULT_TITLE
        block.display_name = ROBBO_ORA_DEFAULT_TITLE
    if should_replace_ora_rubric(block.rubric_criteria):
        block.rubric_criteria = localized_ora_rubric_criteria()
        block.rubric_feedback_prompt = ROBBO_ORA_DEFAULT_RUBRIC_FEEDBACK_PROMPT
        block.rubric_feedback_default_text = ROBBO_ORA_DEFAULT_RUBRIC_FEEDBACK_TEXT
    return block
