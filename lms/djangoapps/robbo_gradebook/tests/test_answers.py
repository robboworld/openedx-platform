# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (gradebook additions). See NOTICE at repository root.

"""«Ответы учащегося» in the gradebook: GET /api/robbo/v1/gradebook/<course>/answers/ (answers.py)."""

import json
from unittest.mock import patch
from urllib.parse import urlencode

from django.urls import reverse
from edx_toggles.toggles.testutils import override_waffle_flag

from submissions import api as submissions_api

from common.djangoapps.student.models import CourseEnrollment, anonymous_id_for_user
from common.djangoapps.student.tests.factories import TEST_PASSWORD, StaffFactory, UserFactory
from lms.djangoapps.courseware.models import StudentModule
from lms.djangoapps.grades.api import CourseGradeFactory
from lms.djangoapps.grades.config.waffle import WRITABLE_GRADEBOOK
from openedx.core.djangolib.testing.utils import skip_unless_lms
from xmodule.modulestore.tests.django_utils import SharedModuleStoreTestCase
from xmodule.modulestore.tests.factories import BlockFactory, CourseFactory

CHOICE_XML = '''<problem>
<multiplechoiceresponse>
<label>How many wheels?</label>
<choicegroup type="MultipleChoice">
<choice correct="false">Two</choice>
<choice correct="true">Four</choice>
</choicegroup>
</multiplechoiceresponse>
</problem>'''

CHECKBOX_XML = '''<problem>
<choiceresponse>
<label>Which are sensors?</label>
<checkboxgroup>
<choice correct="true">Line sensor</choice>
<choice correct="false">Motor</choice>
<choice correct="true">Distance sensor</choice>
</checkboxgroup>
</choiceresponse>
</problem>'''

TEXT_XML = '''<problem>
<stringresponse answer="LED" type="ci">
<label>What lights up?</label>
<additional_answer answer="diode"/>
<textline/>
</stringresponse>
</problem>'''

TWO_QUESTIONS_XML = '''<problem>
<multiplechoiceresponse>
<label>What turns a wheel?</label>
<choicegroup type="MultipleChoice">
<choice correct="true">Motor</choice>
<choice correct="false">Battery</choice>
</choicegroup>
</multiplechoiceresponse>
<stringresponse answer="2" type="ci">
<label>How many motors?</label>
<textline/>
</stringresponse>
</problem>'''

PICTURES_XML = '''<problem>
<multiplechoiceresponse>
<label>Which code is right?</label>
<choicegroup type="MultipleChoice">
<choice correct="true"><img src="/static/code_a.png" alt="Code A"/></choice>
<choice correct="false">None of them <img src="https://example.com/code_b.png" alt="Code B"/>
<choicehint>Look again</choicehint></choice>
</choicegroup>
</multiplechoiceresponse>
</problem>'''


@skip_unless_lms
@override_waffle_flag(WRITABLE_GRADEBOOK, active=True)
class LearnerAnswersViewTests(SharedModuleStoreTestCase):
    """A graded subsection with four problems; one learner, a course team member."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.course = CourseFactory.create()
        chapter = BlockFactory.create(parent=cls.course, category='chapter')
        cls.subsection = BlockFactory.create(
            parent=chapter, category='sequential', display_name='Homework 1', graded=True, format='Homework',
        )
        unit = BlockFactory.create(parent=cls.subsection, category='vertical', display_name='Unit 1')
        cls.choice = BlockFactory.create(parent=unit, category='problem', display_name='Wheels', data=CHOICE_XML)
        cls.checkbox = BlockFactory.create(parent=unit, category='problem', display_name='Sensors', data=CHECKBOX_XML)
        cls.text = BlockFactory.create(parent=unit, category='problem', display_name='Lights', data=TEXT_XML)
        cls.two = BlockFactory.create(parent=unit, category='problem', display_name='Motors', data=TWO_QUESTIONS_XML)
        cls.pictures = BlockFactory.create(parent=unit, category='problem', display_name='Code', data=PICTURES_XML)
        cls.ora = BlockFactory.create(
            parent=unit, category='openassessment', display_name='Robot photo',
            prompt=json.dumps([{'description': '<p>Show your <b>robot</b></p>'}, {'description': 'What can it do?'}]),
        )
        cls.url = reverse('robbo_gradebook:learner_answers', kwargs={'course_id': str(cls.course.id)})

    def setUp(self):
        super().setUp()
        self.learner = UserFactory()
        CourseEnrollment.enroll(self.learner, self.course.id)
        self.staff = StaffFactory(course_key=self.course.id, password=TEST_PASSWORD)
        self.client.login(username=self.staff.username, password=TEST_PASSWORD)

    def answer(self, block, answers, correctness=None, earned=0, possible=1):
        """
        Learner state of a capa problem: `answers` and `correctness` by input number (1, 2...).
        Without correctness the answers are saved but not submitted.
        """
        html_id = block.location.html_id()
        state = {
            'seed': 1,
            'student_answers': {f'{html_id}_{number + 1}_1': value for number, value in answers.items()},
            'has_saved_answers': correctness is None,
            'attempts': 0 if correctness is None else 1,
            'done': correctness is not None,
        }
        if correctness is not None:
            state['correct_map'] = {
                f'{html_id}_{number + 1}_1': {'correctness': value, 'npoints': None, 'msg': '', 'hint': '',
                                              'hintmode': None, 'queuestate': None, 'answervariable': None}
                for number, value in correctness.items()
            }
        StudentModule.objects.create(
            student=self.learner,
            course_id=self.course.id,
            module_state_key=block.location,
            module_type='problem',
            grade=None if correctness is None else earned,
            max_grade=None if correctness is None else possible,
            state=json.dumps(state),
        )

    def submit_response(self, answer):
        """The learner's open response submission (no assessments yet)."""
        submissions_api.create_submission({
            'student_id': anonymous_id_for_user(self.learner, self.course.id),
            'course_id': str(self.course.id),
            'item_id': str(self.ora.location),
            'item_type': 'openassessment',
        }, answer)

    def get(self, **params):
        query = {'user_id': self.learner.id, 'subsection': str(self.subsection.location), **params}
        return self.client.get(f'{self.url}?{urlencode(query)}')

    def problems(self):
        """Problems of the subsection by name, after the grade was computed as on a submission."""
        # A submission persists the subsection grade; without one test settings assume zero.
        CourseGradeFactory().update(self.learner, course_key=self.course.id, force_update_subsections=True)
        response = self.get()
        assert response.status_code == 200, response.content
        return {problem['name']: problem for problem in response.json()['problems']}

    def test_wrong_and_right_answers(self):
        self.answer(self.choice, {1: 'choice_0'}, {1: 'incorrect'})
        self.answer(self.checkbox, {1: ['choice_1', 'choice_0']}, {1: 'incorrect'})
        self.answer(self.two, {1: 'choice_0', 2: '3'}, {1: 'correct', 2: 'incorrect'}, earned=1, possible=2)

        response = self.get()
        assert [problem['name'] for problem in response.json()['problems']] == [
            'Wheels', 'Sensors', 'Lights', 'Motors', 'Code', 'Robot photo',
        ]
        problems = self.problems()

        wheels = problems['Wheels']
        assert wheels['unitName'] == 'Unit 1'
        assert (wheels['earned'], wheels['possible'], wheels['attempts']) == (0, 1, 1)
        assert wheels['correctness'] == 'incorrect'
        assert wheels['answers'] == [{
            'question': 'How many wheels?', 'answer': 'Two', 'files': [],
            'correctAnswer': 'Four', 'correctFiles': [], 'correctness': 'incorrect',
        }]
        # Checkbox choices in problem order, whatever the stored order.
        assert problems['Sensors']['answers'][0]['answer'] == 'Line sensor, Motor'
        assert problems['Sensors']['answers'][0]['correctAnswer'] == 'Line sensor, Distance sensor'

        motors = problems['Motors']
        assert motors['correctness'] == 'partially-correct'
        assert [(a['question'], a['answer'], a['correctness']) for a in motors['answers']] == [
            ('What turns a wheel?', 'Motor', 'correct'),
            ('How many motors?', '3', 'incorrect'),
        ]
        assert motors['answers'][1]['correctAnswer'] == '2'

        lights = problems['Lights']
        assert (lights['correctness'], lights['answers'], lights['attempts']) == (None, [], 0)

    def test_picture_choices(self):
        self.answer(self.pictures, {1: 'choice_1'}, {1: 'incorrect'})
        answer = self.problems()['Code']['answers'][0]
        # The text of a choice without its hint; a picture only choice has no text.
        assert answer['answer'] == 'None of them'
        assert answer['files'] == [
            {'url': 'https://example.com/code_b.png', 'name': 'Code B', 'description': '', 'image': True},
        ]
        assert answer['correctAnswer'] == ''
        [picture] = answer['correctFiles']
        # Course assets become asset URLs.
        assert 'code_a.png' in picture['url'] and not picture['url'].startswith('/static/')
        assert (picture['name'], picture['image']) == ('Code A', True)

    @patch('openassessment.data.get_download_url', lambda key: f'/files/{key}')
    def test_open_response_text_and_files(self):
        self.submit_response({
            'parts': [{'text': 'A robot '}, {'text': 'It follows a line'}],
            'file_keys': ['k1', 'k2'],
            'files_names': ['robot.jpg', 'program.sb3'],
            'files_descriptions': ['Front view', 'Program'],
            'files_sizes': [10, 20],
        })
        photo = self.problems()['Robot photo']
        assert photo['type'] == 'openassessment'
        # Submitted, waiting for the assessments.
        assert (photo['correctness'], photo['awaitingGrade']) == (None, True)
        assert [(a['question'], a['answer']) for a in photo['answers']] == [
            ('Show your robot', 'A robot'), ('What can it do?', 'It follows a line'),
        ]
        assert photo['answers'][0]['files'] == []
        assert photo['answers'][1]['files'] == [
            {'url': '/files/k1', 'name': 'robot.jpg', 'description': 'Front view', 'image': True},
            {'url': '/files/k2', 'name': 'program.sb3', 'description': 'Program', 'image': False},
        ]

    @patch('openassessment.data.get_download_url', lambda key: f'/files/{key}')
    def test_open_response_files_only(self):
        # An early submission shape: files without names.
        self.submit_response({'parts': [], 'file_keys': ['k1'], 'files_descriptions': ['']})
        [answer] = self.problems()['Robot photo']['answers']
        assert (answer['question'], answer['answer']) == ('Show your robot', '')
        assert [file['url'] for file in answer['files']] == ['/files/k1']

    def test_open_response_without_submission(self):
        photo = self.problems()['Robot photo']
        assert (photo['answers'], photo['awaitingGrade'], photo['correctness']) == ([], False, None)

    def test_text_answer_alternatives_without_markup(self):
        self.answer(self.text, {1: 'lamp'}, {1: 'incorrect'})
        answer = self.problems()['Lights']['answers'][0]
        assert answer['answer'] == 'lamp'
        assert answer['correctAnswer'] == 'LED or diode'

    def test_saved_answer_is_not_judged(self):
        self.answer(self.text, {1: 'lamp'})
        lights = self.problems()['Lights']
        assert lights['saved'] is True
        assert lights['correctness'] is None
        assert lights['answers'][0]['answer'] == 'lamp'
        assert lights['answers'][0]['correctness'] is None

    def test_unreadable_problem_keeps_the_others(self):
        self.answer(self.choice, {1: 'choice_1'}, {1: 'correct'}, earned=1)
        with patch('lms.djangoapps.robbo_gradebook.answers.LoncapaProblem.find_question_label', side_effect=ValueError):
            problems = self.problems()
        assert problems['Wheels']['answersError'] is True
        assert problems['Wheels']['answers'] == []
        assert problems['Wheels']['correctness'] == 'correct'
        assert problems['Sensors']['answersError'] is False

    def test_course_team_only(self):
        self.client.login(username=self.learner.username, password=TEST_PASSWORD)
        assert self.get().status_code == 403

    def test_writable_gradebook_only(self):
        with override_waffle_flag(WRITABLE_GRADEBOOK, active=False):
            assert self.get().status_code == 403

    def test_learners_of_the_course_only(self):
        assert self.get(user_id=UserFactory().id).status_code == 404
        assert self.get(user_id=0).status_code == 404

    def test_subsections_of_the_course_only(self):
        other_course = CourseFactory.create()
        other_subsection = BlockFactory.create(
            parent=BlockFactory.create(parent=other_course, category='chapter'), category='sequential',
        )
        assert self.get(subsection=str(other_subsection.location)).status_code == 404
        assert self.get(subsection=str(self.choice.location)).status_code == 404

    def test_bad_parameters(self):
        assert self.get(user_id='me').status_code == 400
        assert self.get(subsection='nope').status_code == 400
