# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
"""Tests of the ORA retake (cms/djangoapps/contentstore/robbo_ora_retake.py)."""

from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import ddt
from django.test import TestCase
from opaque_keys.edx.keys import CourseKey
from openassessment.assessment.models.staff import StaffWorkflow

from cms.djangoapps.contentstore import robbo_ora_retake as retake
from common.djangoapps.student.tests.factories import UserFactory
from lms.djangoapps.robbo_ora.models import OraRetakeGrant

COURSE_KEY = CourseKey.from_string('course-v1:Robbo+Retake+2026')
ORA_LOCATION = 'block-v1:Robbo+Retake+2026+type@openassessment+block@ora'


def make_block(**overrides):
    """A learner's ORA block: individual, graded, closed for submissions only when told so."""
    fields = {
        'teams_enabled': False,
        'assessment_steps': ['staff-assessment'],
        'submission_uuid': str(uuid4()),
        'workflow_data': SimpleNamespace(status='done'),
        'robbo_allow_retake': False,
        'robbo_retake_granted': False,
        'robbo_closed_by_dates': Mock(return_value=(False, None, None, None)),
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


@ddt.ddt
@patch('openassessment.xblock.utils.allow_resubmission.has_grade_in_process', Mock(return_value=False))
class AvailableRetakeTests(TestCase):
    """Who may retake and how."""

    def grant(self, block):
        OraRetakeGrant.objects.create(submission_uuid=block.submission_uuid, course_id=COURSE_KEY)

    def test_nothing_enabled(self):
        assert retake.available_retake(make_block()) is None

    def test_option(self):
        assert retake.available_retake(make_block(robbo_allow_retake=True)) == retake.RETAKE_OPTION

    def test_option_stops_at_the_deadline(self):
        closed = Mock(return_value=(True, 'due', None, None))
        block = make_block(robbo_allow_retake=True, robbo_closed_by_dates=closed)
        assert retake.available_retake(block) is None

    def test_grant_ignores_the_deadline(self):
        block = make_block(robbo_closed_by_dates=Mock(return_value=(True, 'due', None, None)))
        self.grant(block)
        assert retake.available_retake(block) == retake.RETAKE_GRANTED

    @ddt.data('waiting', 'staff', 'cancelled', None)
    def test_only_a_final_grade(self, status):
        block = make_block(robbo_allow_retake=True, workflow_data=SimpleNamespace(status=status))
        assert retake.available_retake(block) is None

    def test_not_while_being_graded(self):
        block = make_block(robbo_allow_retake=True)
        with patch('openassessment.xblock.utils.allow_resubmission.has_grade_in_process', return_value=True):
            assert retake.available_retake(block) is None

    @ddt.data(
        {'teams_enabled': True},
        {'assessment_steps': ['peer-assessment', 'staff-assessment']},
        {'submission_uuid': None},
    )
    def test_unsupported(self, overrides):
        assert retake.available_retake(make_block(robbo_allow_retake=True, **overrides)) is None


class RetakeGrantTests(TestCase):
    """The grader's checkbox."""

    def setUp(self):
        super().setUp()
        self.grader = UserFactory()
        self.uuid = str(uuid4())
        store = patch('xmodule.modulestore.django.modulestore').start()
        store.return_value.get_item.return_value = make_block()
        self.addCleanup(patch.stopall)
        self.store = store

    def test_tick_and_untick(self):
        retake.set_retake_grant(ORA_LOCATION, self.uuid, True, self.grader)
        grant = OraRetakeGrant.objects.get(submission_uuid=self.uuid)
        assert grant.granted_by == self.grader
        assert grant.course_id == COURSE_KEY
        assert retake.retake_granted(self.uuid)

        retake.set_retake_grant(ORA_LOCATION, self.uuid, False, self.grader)
        assert not retake.retake_granted(self.uuid)

    def test_grading_twice_keeps_one_grant(self):
        retake.set_retake_grant(ORA_LOCATION, self.uuid, True, self.grader)
        retake.set_retake_grant(ORA_LOCATION, self.uuid, True, self.grader)
        assert OraRetakeGrant.objects.filter(submission_uuid=self.uuid).count() == 1

    def test_older_page_without_the_checkbox_changes_nothing(self):
        retake.set_retake_grant(ORA_LOCATION, self.uuid, True, self.grader)
        retake.set_retake_grant(ORA_LOCATION, self.uuid, None, self.grader)
        assert retake.retake_granted(self.uuid)

    def test_unsupported_assignment_gets_no_grant(self):
        self.store.return_value.get_item.return_value = make_block(teams_enabled=True)
        retake.set_retake_grant(ORA_LOCATION, self.uuid, True, self.grader)
        assert not retake.retake_granted(self.uuid)


class StartRetakeTests(TestCase):
    """The retake forgets the submission, not the grade."""

    def start(self, block, kind):
        answer = {'answer': {'parts': [{'text': 'ответ'}]}}
        with patch('submissions.api.get_submission', return_value=answer):
            retake.start_retake(block, kind)

    def test_grant_is_spent_and_lifts_the_deadline(self):
        block = make_block()
        uuid = block.submission_uuid
        OraRetakeGrant.objects.create(submission_uuid=uuid, course_id=COURSE_KEY)
        self.start(block, retake.RETAKE_GRANTED)
        assert block.submission_uuid is None
        assert block.robbo_retake_granted is True
        assert block.saved_response == '{"parts": [{"text": "\\u043e\\u0442\\u0432\\u0435\\u0442"}]}'
        assert not retake.retake_granted(uuid)

    def test_option_keeps_the_deadline(self):
        block = make_block(robbo_retake_granted=True)
        self.start(block, retake.RETAKE_OPTION)
        assert block.robbo_retake_granted is False

    def test_earlier_attempts_leave_the_grading_lists(self):
        earlier, new, other_item = str(uuid4()), str(uuid4()), str(uuid4())
        for uuid in (earlier, new, other_item):
            StaffWorkflow.objects.create(course_id=str(COURSE_KEY), item_id='ora', submission_uuid=uuid)
        block = SimpleNamespace(get_student_item_dict=dict)
        submissions = [{'uuid': new}, {'uuid': earlier}]
        with patch('submissions.api.get_submissions', return_value=submissions):
            retake.close_earlier_attempts(block, new)
        assert StaffWorkflow.objects.get(submission_uuid=earlier).cancelled_at is not None
        assert StaffWorkflow.objects.get(submission_uuid=new).cancelled_at is None
        assert StaffWorkflow.objects.get(submission_uuid=other_item).cancelled_at is None


class RetakeBlockTests(TestCase):
    """The block inserted into the rendered steps."""

    GRADE_STEP = 'legacy/grade/oa_grade_complete.html'
    RESPONSE_STEP = 'legacy/response/oa_response.html'

    def test_button_on_the_grade_step(self):
        block = make_block(robbo_allow_retake=True, runtime=Mock())
        block.runtime.handler_url.return_value = '/handler/robbo_retake'
        with patch('openassessment.xblock.utils.allow_resubmission.has_grade_in_process', return_value=False):
            html = retake.insert_retake_block(block, self.GRADE_STEP, '<div class="step__content"><p>x</p></div>')
        assert 'data-url="/handler/robbo_retake"' in html
        assert html.index('robbo-ora-retake__start') < html.index('<p>x</p>')

    def test_no_button_without_a_retake(self):
        html = '<div class="step__content"></div>'
        assert retake.insert_retake_block(make_block(), self.GRADE_STEP, html) == html

    def test_other_steps_stay_as_they_are(self):
        html = '<div class="step__content"></div>'
        assert retake.insert_retake_block(make_block(), 'legacy/grade/oa_grade_waiting.html', html) == html

    def test_grade_and_comments_while_working_on_a_retake(self):
        block = make_block(submission_uuid=None, get_student_item_dict=dict)
        score = {'submission_uuid': 'old', 'points_earned': 6, 'points_possible': 10}
        assessment = {
            'feedback': 'Переделай <b>вывод</b>',
            'parts': [{
                'criterion': {'name': 'ideas', 'label': 'Идеи'},
                'option': {'label': 'Хорошо'},
                'feedback': 'Мало примеров',
            }],
        }
        with patch('submissions.api.get_score', return_value=score), patch(
            'openassessment.assessment.api.staff.get_latest_staff_assessment', return_value=assessment,
        ):
            html = retake.insert_retake_block(block, self.RESPONSE_STEP, '<div class="wrapper--step__content"></div>')
        assert '6' in html and '10' in html
        assert 'Переделай &lt;b&gt;вывод&lt;/b&gt;' in html
        assert 'Хорошо' in html and 'Мало примеров' in html

    def test_first_attempt_has_no_notice(self):
        block = make_block(submission_uuid=None, get_student_item_dict=dict)
        html = '<div class="wrapper--step__content"></div>'
        with patch('submissions.api.get_score', return_value=None):
            assert retake.insert_retake_block(block, self.RESPONSE_STEP, html) == html
