# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (gradebook additions). See NOTICE at repository root.

"""PDF report of the gradebook: learners by last activity and progress by unit (progress.py)."""

import json
from datetime import timedelta
from urllib.parse import urlencode

from django.urls import reverse
from django.utils import timezone
from edx_toggles.toggles.testutils import override_waffle_flag

from common.djangoapps.student.models import CourseEnrollment
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


@skip_unless_lms
@override_waffle_flag(WRITABLE_GRADEBOOK, active=True)
class GradebookReportTests(SharedModuleStoreTestCase):
    """Section 1 / Homework 1 with two units (two and one problems); an empty unit; a text unit."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.course = CourseFactory.create()
        chapter = BlockFactory.create(parent=cls.course, category='chapter', display_name='Section 1')
        cls.subsection = BlockFactory.create(
            parent=chapter, category='sequential', display_name='Homework 1', graded=True, format='Homework',
        )
        unit1 = BlockFactory.create(parent=cls.subsection, category='vertical', display_name='Unit 1')
        cls.p1 = BlockFactory.create(parent=unit1, category='problem', display_name='P1', data=CHOICE_XML)
        cls.p2 = BlockFactory.create(parent=unit1, category='problem', display_name='P2', data=CHOICE_XML)
        unit2 = BlockFactory.create(parent=cls.subsection, category='vertical', display_name='Unit 2')
        cls.p3 = BlockFactory.create(parent=unit2, category='problem', display_name='P3', data=CHOICE_XML)
        text_unit = BlockFactory.create(parent=cls.subsection, category='vertical', display_name='Reading')
        BlockFactory.create(parent=text_unit, category='html', display_name='Text')
        # A section without anything scored is left out.
        empty = BlockFactory.create(parent=cls.course, category='chapter', display_name='Intro')
        BlockFactory.create(parent=empty, category='sequential', display_name='Welcome')
        cls.learners_url = reverse('robbo_gradebook:course_learners', kwargs={'course_id': str(cls.course.id)})
        cls.progress_url = reverse('robbo_gradebook:learner_progress', kwargs={'course_id': str(cls.course.id)})

    def setUp(self):
        super().setUp()
        self.learner = UserFactory(username='boris')
        CourseEnrollment.enroll(self.learner, self.course.id)
        self.staff = StaffFactory(course_key=self.course.id, password=TEST_PASSWORD)
        self.client.login(username=self.staff.username, password=TEST_PASSWORD)

    def submit(self, user, block, earned, possible=1):
        """A submitted answer of `user` with these points."""
        StudentModule.objects.create(
            student=user, course_id=self.course.id, module_state_key=block.location, module_type='problem',
            grade=earned, max_grade=possible, state=json.dumps({'attempts': 1, 'done': True}),
        )

    def progress(self, user=None, **params):
        query = {'user_id': (user or self.learner).id, **params}
        return self.client.get(f'{self.progress_url}?{urlencode(query)}')

    def test_learners_by_last_activity(self):
        anna = UserFactory(username='anna')
        zoe = UserFactory(username='zoe')
        left = UserFactory(username='left')
        for user in (anna, zoe, left):
            CourseEnrollment.enroll(user, self.course.id)
        CourseEnrollment.unenroll(left, self.course.id)
        self.submit(self.learner, self.p1, 1)
        self.submit(anna, self.p1, 0)
        # Boris was active later than Anna; Zoe never.
        StudentModule.objects.filter(student=anna).update(modified=timezone.now() - timedelta(days=2))

        response = self.client.get(self.learners_url)
        assert response.status_code == 200, response.content
        # The course name for the report, not its id.
        assert response.json()['course'] == {'id': str(self.course.id), 'name': self.course.display_name}
        learners = response.json()['learners']
        # Enrolled now only (not Left); the course team is not enrolled here.
        assert [learner['username'] for learner in learners] == ['boris', 'anna', 'zoe']
        boris = learners[0]
        assert set(boris) == {'id', 'username', 'fullName', 'email', 'lastActivity'}
        assert boris['lastActivity'] and learners[-1]['lastActivity'] is None
        assert 'left' not in [learner['username'] for learner in learners]

    def test_progress_by_unit(self):
        self.submit(self.learner, self.p1, 1)
        self.submit(self.learner, self.p2, 1)
        self.submit(self.learner, self.p3, 0)
        CourseGradeFactory().update(self.learner, course_key=self.course.id, force_update_subsections=True)

        response = self.progress()
        assert response.status_code == 200, response.content
        data = response.json()
        assert data['learner']['username'] == 'boris'
        assert (data['passedUnits'], data['units']) == (1, 2)
        [section] = data['sections']
        assert section['name'] == 'Section 1'
        [homework] = section['subsections']
        assert (homework['name'], homework['graded'], homework['format']) == ('Homework 1', True, 'Homework')
        assert (homework['earned'], homework['possible']) == (2, 3)
        # The text unit has no points and is left out; a unit passes with all of its points only.
        assert homework['units'] == [
            {'name': 'Unit 1', 'earned': 2, 'possible': 2, 'passed': True},
            {'name': 'Unit 2', 'earned': 0, 'possible': 1, 'passed': False},
        ]
        assert data['percent'] == CourseGradeFactory().read(self.learner, course_key=self.course.id).percent

    def test_partial_unit_is_not_passed(self):
        self.submit(self.learner, self.p1, 1)
        CourseGradeFactory().update(self.learner, course_key=self.course.id, force_update_subsections=True)
        unit1 = self.progress().json()['sections'][0]['subsections'][0]['units'][0]
        assert (unit1['earned'], unit1['possible'], unit1['passed']) == (1, 2, False)

    def test_course_team_only(self):
        self.client.login(username=self.learner.username, password=TEST_PASSWORD)
        assert self.client.get(self.learners_url).status_code == 403
        assert self.progress().status_code == 403

    def test_writable_gradebook_only(self):
        with override_waffle_flag(WRITABLE_GRADEBOOK, active=False):
            assert self.client.get(self.learners_url).status_code == 403
            assert self.progress().status_code == 403

    def test_learners_of_the_course_only(self):
        assert self.progress(user=UserFactory()).status_code == 404
        assert self.progress(user_id='me').status_code == 400
