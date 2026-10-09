# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Instructor dashboard «Ответы в свободной форме»: the edx-ora2 listing (Backgrid table
# + summary row) gets a hint next to every counter of the summary row and Russian labels.
# The page script is lms/static/js/robbo-ora-instructor-listing.js.

"""Hints and labels for the ORA listing in the LMS instructor dashboard."""

import json
import logging

from django.utils.translation import gettext as _

from cms.djangoapps.contentstore.robbo_ora_i18n import robbo_ora_russian_active

log = logging.getLogger(__name__)

# Summary column (edx-ora2 oa_course_items_listing.js) -> hint, EN msgid.
LISTING_HINTS = {
    'parent_name': "Course units that contain open response assignments.",
    'name': "Open response assignments in the course.",
    'total': "All submitted responses: the sum of the steps in the columns to the right.",
    'training': (
        "Responses whose authors are practising assessment on sample responses before peer assessment."
    ),
    'peer': "Responses whose authors are assessing other learners' responses.",
    'self': "Responses whose authors are assessing their own response.",
    'waiting': (
        "Responses waiting for assessments from other learners; their authors have completed all their own steps."
    ),
    'staff': "Responses waiting for an assessment by the course team.",
    'done': "Responses whose assessment is complete and a final grade has been given.",
}

HINT_BUTTON_LABEL = "What does “{label}” mean?"

LISTING_RU = {
    LISTING_HINTS['parent_name']: "Блоки курса, в которых есть задания с развёрнутым ответом.",
    LISTING_HINTS['name']: "Задания с развёрнутым ответом в курсе.",
    LISTING_HINTS['total']: "Все отправленные ответы — сумма по этапам в столбцах справа.",
    LISTING_HINTS['training']: (
        "Ответы учащихся, которые сейчас учатся оценивать: разбирают примеры перед взаимооценкой."
    ),
    LISTING_HINTS['peer']: "Ответы учащихся, которые сейчас оценивают работы других учащихся.",
    LISTING_HINTS['self']: "Ответы учащихся, которые сейчас оценивают собственную работу.",
    LISTING_HINTS['waiting']: (
        "Ответы, которые ждут оценок от других учащихся: автор уже прошёл все свои этапы."
    ),
    LISTING_HINTS['staff']: "Ответы, которые ждут оценки команды курса.",
    LISTING_HINTS['done']: "Ответы, по которым оценивание завершено и выставлена итоговая оценка.",
    HINT_BUTTON_LABEL: "Что означает «{label}»?",
}

# Russian labels that replace edx-ora2 ones: untranslated («Staff Grader») or misleading
# («Оценка» for the assignment name, «Сотрудник» for the course team step).
TABLE_LABELS_RU = {
    'name': "Задание",
    'staff': "Команда курса",
    'staff_grader': "Проверка ответов",
}
SUMMARY_LABELS_RU = {
    'staff': "Команда курса",
}
# Text of the edx-ora2 link in the «Staff Grader» column, keyed by its EN text.
LINK_TEXTS_RU = {
    "View and grade responses": "Проверить и оценить",
    "Demo the new Grading Experience": "Попробовать новый интерфейс оценивания",
}


def _message(msgid):
    if robbo_ora_russian_active():
        return LISTING_RU.get(msgid, _(msgid))
    return _(msgid)


def listing_config():
    """Hints and label overrides for the page script, in the request language."""
    russian = robbo_ora_russian_active()
    return {
        'hints': {column: _message(msgid) for column, msgid in LISTING_HINTS.items()},
        'hintButtonLabel': _message(HINT_BUTTON_LABEL),
        'tableLabels': TABLE_LABELS_RU if russian else {},
        'summaryLabels': SUMMARY_LABELS_RU if russian else {},
        'linkTexts': LINK_TEXTS_RU if russian else {},
    }


def _config_script():
    payload = json.dumps(listing_config(), ensure_ascii=False).replace('<', '\\u003c')
    return f'<script type="application/json" id="robbo-ora-listing-config">{payload}</script>'


def patch_ora_instructor_listing():
    """Wrap OpenAssessmentBlock.ora_blocks_listing_view with the Robbo hints."""
    from django.contrib.staticfiles.storage import staticfiles_storage
    from openassessment.xblock.openassessmentblock import OpenAssessmentBlock

    if getattr(OpenAssessmentBlock, '_robbo_instructor_listing_patched', False):
        return

    original_view = OpenAssessmentBlock.ora_blocks_listing_view

    def ora_blocks_listing_view(self, context=None):
        fragment = original_view(self, context)
        try:
            script_url = staticfiles_storage.url('js/robbo-ora-instructor-listing.js')
        except ValueError:  # not collected yet: keep the stock listing working
            log.warning('robbo-ora-instructor-listing.js is missing from staticfiles')
            return fragment
        fragment.content += _config_script()
        fragment.add_javascript_url(script_url)
        return fragment

    OpenAssessmentBlock.ora_blocks_listing_view = ora_blocks_listing_view
    OpenAssessmentBlock._robbo_instructor_listing_patched = True
