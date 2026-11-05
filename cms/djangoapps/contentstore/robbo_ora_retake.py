# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only

"""
Robbo ORA: a new response after the grade (CMS + LMS).

Two independent ways in: the block option «Пересдача после оценки» (every learner, after every
grade, until the submission deadline) and the grader's «Разрешить пересдачу» (one learner, one
attempt, also after the deadline; a row of OraRetakeGrant for the graded submission).

A retake only forgets the block's `submission_uuid`: the graded submission, its assessments and
its Score stay, so the grade counts until the new response is graded. Score summaries then keep
the latest score, which is why the new grade replaces the old one even when it is lower.
"""

import json
import logging
from pathlib import Path

from django.apps import apps
from django.utils.timezone import now

from .robbo_ora_i18n import robbo_ora_catalog_message

log = logging.getLogger(__name__)

RETAKE_GRANTED = 'granted'
RETAKE_OPTION = 'option'

_ROBBO_ORA_APP = 'lms.djangoapps.robbo_ora'
_RETAKE_TEMPLATE = Path(__file__).resolve().parent / 'templates' / 'legacy' / 'robbo_ora_retake.html'
_GRADE_STEP = 'legacy/grade/oa_grade_complete.html'
_RESPONSE_STEP = 'legacy/response/oa_response.html'
# Inserted into the rendered step rather than into a copy of the template: `oa_response.html` is
# overridden for Russian only and the grade step not at all.
_STEP_ANCHORS = {
    _GRADE_STEP: '<div class="step__content">',
    _RESPONSE_STEP: '<div class="wrapper--step__content">',
}


def retake_supported(block):
    """Same limit as the stock resubmission: team and peer workflows are tied to one submission."""
    return not block.teams_enabled and 'peer-assessment' not in block.assessment_steps


def _grant_model():
    """OraRetakeGrant, or None in Studio: grading tools and the app itself live in LMS only."""
    if not apps.is_installed(_ROBBO_ORA_APP):
        return None
    return apps.get_model('robbo_ora', 'OraRetakeGrant')


def retake_granted(submission_uuid):
    """Did the grader allow a retake of this submission?"""
    grant_model = _grant_model()
    return bool(grant_model) and grant_model.objects.filter(submission_uuid=submission_uuid).exists()


def set_retake_grant(ora_location, submission_uuid, allowed, user):
    """Save the grader's checkbox for the submission; None (an older open page) keeps it as it is."""
    from opaque_keys.edx.keys import UsageKey
    from xmodule.modulestore.django import modulestore

    grant_model = _grant_model()
    if allowed is None or grant_model is None:
        return
    if not allowed:
        grant_model.objects.filter(submission_uuid=submission_uuid).delete()
        return
    usage_key = UsageKey.from_string(ora_location)
    if retake_supported(modulestore().get_item(usage_key)):
        grant_model.objects.update_or_create(
            submission_uuid=submission_uuid,
            defaults={'course_id': usage_key.course_key, 'granted_by': user},
        )


def available_retake(block):
    """How the learner of the block may retake now: RETAKE_GRANTED, RETAKE_OPTION or None."""
    from openassessment.xblock.utils.allow_resubmission import has_grade_in_process

    submission_uuid = block.submission_uuid
    if not submission_uuid or not retake_supported(block):
        return None
    if block.workflow_data.status != 'done' or has_grade_in_process(submission_uuid):
        return None
    if retake_granted(submission_uuid):
        return RETAKE_GRANTED
    if block.robbo_allow_retake and not block.robbo_closed_by_dates(step='submission')[0]:
        return RETAKE_OPTION
    return None


def start_retake(block, kind):
    """Open the response step again, with the text of the graded response as a draft."""
    from submissions import api as submissions_api

    submission_uuid = block.submission_uuid
    answer = submissions_api.get_submission(submission_uuid).get('answer', {})
    block.saved_response = json.dumps({'parts': answer.get('parts', [])})
    block.has_saved = True
    block.robbo_retake_granted = kind == RETAKE_GRANTED
    block.submission_uuid = None
    grant_model = _grant_model()
    if grant_model:
        grant_model.objects.filter(submission_uuid=submission_uuid).delete()


def _earlier_attempts(block, submission_uuid):
    """UUIDs of the learner's other submissions of the block."""
    from submissions import api as submissions_api

    return [
        submission['uuid']
        for submission in submissions_api.get_submissions(block.get_student_item_dict())
        if submission['uuid'] != submission_uuid
    ]


def close_earlier_attempts(block, submission_uuid):
    """
    Take the earlier attempts of the learner out of the grading lists, as ORA does with a removed
    response: a list shows one entry per learner, and an old attempt must not be regraded over the
    new grade. Their scores stay.
    """
    from openassessment.assessment.models.staff import StaffWorkflow

    earlier = _earlier_attempts(block, submission_uuid)
    if earlier:
        StaffWorkflow.objects.filter(submission_uuid__in=earlier, cancelled_at=None).update(cancelled_at=now())


def _grade_step_context(block):
    """The «Пересдать» button of the grade step."""
    kind = available_retake(block)
    if kind is None:
        return None
    return {
        'robbo_retake_kind': kind,
        'robbo_retake_url': block.runtime.handler_url(block, 'robbo_retake'),
    }


def _response_step_context(block):
    """The grade and the comments being worked on: the grade step is gone during a retake."""
    from openassessment.assessment.api import staff as staff_api
    from submissions import api as submissions_api

    if block.submission_uuid or not retake_supported(block):
        return None
    score = submissions_api.get_score(block.get_student_item_dict())
    if not score:
        return None
    assessment = staff_api.get_latest_staff_assessment(score['submission_uuid']) or {}
    return {
        'robbo_retake_grade': robbo_ora_catalog_message(
            'Your current grade is %(earned)s out of %(possible)s. It stays until the new response is graded.',
            earned=score['points_earned'],
            possible=score['points_possible'],
        ),
        'robbo_retake_feedback': assessment.get('feedback', ''),
        'robbo_retake_criteria': [
            {
                'label': part['criterion']['label'] or part['criterion']['name'],
                'option': (part.get('option') or {}).get('label', ''),
                'feedback': part.get('feedback', ''),
            }
            for part in assessment.get('parts', [])
        ],
    }


def insert_retake_block(block, path, html):
    """HTML of a rendered ORA step with the retake block, when the step needs one."""
    from django.template import engines

    anchor = _STEP_ANCHORS.get(path)
    if anchor is None or anchor not in html:
        return html
    context = _grade_step_context(block) if path == _GRADE_STEP else _response_step_context(block)
    if context is None:
        return html
    fragment = engines['django'].from_string(_RETAKE_TEMPLATE.read_text(encoding='utf-8')).render(context)
    return html.replace(anchor, anchor + fragment, 1)


def patch_ora_retake(open_assessment_block):
    """Learner handler, deadline of a granted retake and earlier attempts (CMS + LMS)."""
    from openassessment.xblock.utils import allow_resubmission as allow_resubmission_module
    from submissions.errors import SubmissionNotFoundError
    from xblock.core import XBlock

    original_is_closed = open_assessment_block.is_closed
    original_create_workflow = open_assessment_block.create_workflow
    original_cancel_workflow = open_assessment_block._cancel_workflow  # pylint: disable=protected-access
    original_allow_learner_resubmissions = allow_resubmission_module.allow_learner_resubmissions

    def is_closed(self, step=None, course_staff=None):
        result = original_is_closed(self, step=step, course_staff=course_staff)
        if result[0] and result[1] == 'due' and self.robbo_retake_granted:
            return (False, None) + tuple(result[2:])
        return result

    def create_workflow(self, submission_uuid):
        original_create_workflow(self, submission_uuid)
        close_earlier_attempts(self, submission_uuid)

    def _cancel_workflow(self, submission_uuid, comments, requesting_user_id=None):
        # clear_student_state walks all submissions, but its reset_score of the first one deletes
        # the others too: without this «Удалить состояние слушателя» stops halfway after a retake.
        try:
            return original_cancel_workflow(self, submission_uuid, comments, requesting_user_id)
        except SubmissionNotFoundError:
            return {'success': True, 'msg': ''}

    def allow_learner_resubmissions(config_data):
        # The stock reset deletes the learner's state, and with it the grade that must stay.
        block = config_data._block  # pylint: disable=protected-access
        return original_allow_learner_resubmissions(config_data) and not _earlier_attempts(
            block, block.submission_uuid,
        )

    def robbo_retake(self, data, suffix=''):  # pylint: disable=unused-argument
        kind = available_retake(self)
        if kind is None:
            return {'success': False, 'msg': robbo_ora_catalog_message('This response cannot be retaken now.')}
        start_retake(self, kind)
        return {'success': True, 'msg': ''}

    open_assessment_block.robbo_closed_by_dates = original_is_closed
    open_assessment_block.is_closed = is_closed
    open_assessment_block.create_workflow = create_workflow
    open_assessment_block._cancel_workflow = _cancel_workflow  # pylint: disable=protected-access
    open_assessment_block.robbo_retake = XBlock.json_handler(robbo_retake)
    allow_resubmission_module.allow_learner_resubmissions = allow_learner_resubmissions
