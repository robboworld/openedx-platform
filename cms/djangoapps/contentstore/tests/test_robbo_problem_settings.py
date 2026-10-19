# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution. See NOTICE at repository root.

"""
«Настроить задачи» of a unit, subsection, section or course (cms/djangoapps/contentstore/robbo_problem_settings.py).
"""

import json

from django.urls import reverse

from cms.djangoapps.contentstore.robbo_problem_settings import _with_shuffle
from cms.djangoapps.contentstore.tests.utils import CourseTestCase
from xmodule.modulestore import ModuleStoreEnum
from xmodule.modulestore.tests.factories import BlockFactory

SINGLE = """<problem>
<multiplechoiceresponse>
<p>Sky?</p>
<choicegroup type="MultipleChoice">
<choice correct="false">Red</choice>
<choice correct="true">Blue</choice>
</choicegroup>
</multiplechoiceresponse>
</problem>"""
MULTI = """<problem><choiceresponse><checkboxgroup><choice correct="true">2</choice>
<choice correct="false">3</choice></checkboxgroup></choiceresponse></problem>"""
SCRIPTED = """<problem><script type="loncapa/python">x = 1</script>
<multiplechoiceresponse><choicegroup><choice correct="true">A</choice></choicegroup></multiplechoiceresponse></problem>"""
TEXT = """<problem><stringresponse answer="Moscow"><textline/></stringresponse></problem>"""


class ProblemSettingsTest(CourseTestCase):
    """A published section with choice problems, a scripted one and a text one, and another section."""

    def setUp(self):
        super().setUp()
        self.section = BlockFactory.create(parent=self.course, category='chapter', user_id=self.user.id)
        sequence = BlockFactory.create(parent=self.section, category='sequential', user_id=self.user.id)
        self.unit = BlockFactory.create(parent=sequence, category='vertical', user_id=self.user.id)
        self.single, self.multi, self.scripted, self.text = (
            BlockFactory.create(parent=self.unit, category='problem', data=data, user_id=self.user.id)
            for data in (SINGLE, MULTI, SCRIPTED, TEXT)
        )
        self.store.publish(self.section.location, self.user.id)
        other_section = BlockFactory.create(parent=self.course, category='chapter', user_id=self.user.id)
        other_unit = BlockFactory.create(
            parent=BlockFactory.create(parent=other_section, category='sequential', user_id=self.user.id),
            category='vertical', user_id=self.user.id,
        )
        self.other = BlockFactory.create(parent=other_unit, category='problem', data=SINGLE, user_id=self.user.id)

    def url(self, location):
        return reverse('robbo_problem_settings', kwargs={'usage_key_string': str(location)})

    def apply(self, location, settings, client=None):
        return (client or self.client).post(self.url(location), json.dumps(settings), content_type='application/json')

    def problem(self, block, branch=ModuleStoreEnum.Branch.draft_preferred):
        with self.store.branch_setting(branch, self.course.id):
            return self.store.get_item(block.location)

    def test_summary(self):
        response = self.client.get(self.url(self.section.location))
        assert response.status_code == 200
        assert response.json() == {'problems': 4, 'choice_problems': 2, 'skipped_choice_problems': 1}
        assert self.client.get(self.url(self.course.location)).json()['problems'] == 5

    def test_applies_to_problems_inside(self):
        response = self.apply(self.section.location, {
            'shuffle': 'every_attempt',
            'max_attempts': 'unlimited',
            'show_reset_button': True,
            'showanswer': 'after_attempts',
            'attempts_before_showanswer_button': 2,
            'submission_wait_seconds': 30,
        })
        assert response.status_code == 200
        assert response.json()['changed'] == 4
        for block in (self.single, self.multi):
            # published problems stay published, with the change
            for branch in (ModuleStoreEnum.Branch.draft_preferred, ModuleStoreEnum.Branch.published_only):
                problem = self.problem(block, branch)
                assert 'shuffle="true"' in problem.data
                assert problem.rerandomize == 'always'
        single = self.problem(self.single)
        assert single.data == SINGLE.replace('type="MultipleChoice"', 'type="MultipleChoice" shuffle="true"')
        for block in (self.scripted, self.text):
            problem = self.problem(block)
            assert 'shuffle' not in problem.data
            assert not problem.fields['rerandomize'].is_set_on(problem)
        for block in (self.single, self.scripted, self.text):
            problem = self.problem(block)
            assert problem.fields['max_attempts'].is_set_on(problem) and problem.max_attempts is None
            assert problem.show_reset_button is True
            assert problem.showanswer == 'after_attempts'
            assert problem.attempts_before_showanswer_button == 2
            assert problem.submission_wait_seconds == 30
        other = self.problem(self.other)
        assert 'shuffle' not in other.data and not other.fields['show_reset_button'].is_set_on(other)

    def test_unpublished_edits_stay_unpublished(self):
        draft = self.problem(self.text)
        draft.display_name = 'Draft title'
        self.store.update_item(draft, self.user.id)
        self.apply(self.unit.location, {'show_reset_button': True})
        published = self.problem(self.text, ModuleStoreEnum.Branch.published_only)
        assert published.display_name != 'Draft title'
        assert not published.fields['show_reset_button'].is_set_on(published)
        assert self.problem(self.text).show_reset_button is True
        assert self.problem(self.single, ModuleStoreEnum.Branch.published_only).show_reset_button is True

    def test_turns_shuffle_off(self):
        self.apply(self.unit.location, {'shuffle': 'per_student'})
        assert self.problem(self.multi).rerandomize == 'per_student'
        response = self.apply(self.unit.location, {'shuffle': 'off'})
        assert response.json()['changed'] == 2
        for block, data in ((self.single, SINGLE), (self.multi, MULTI)):
            problem = self.problem(block)
            assert problem.data == data
            assert not problem.fields['rerandomize'].is_set_on(problem)

    def test_unchanged_problems_are_not_saved_again(self):
        self.apply(self.unit.location, {'shuffle': 'per_student', 'max_attempts': 3})
        response = self.apply(self.unit.location, {'shuffle': 'per_student', 'max_attempts': 3})
        assert response.json()['changed'] == 0

    def test_invalid_settings(self):
        for settings in ({'shuffle': 'sometimes'}, {'max_attempts': 0}, {'showanswer': 'after_attempts'},
                         {'show_reset_button': 'yes'}, {'submission_wait_seconds': -1}, ['shuffle']):
            assert self.apply(self.unit.location, settings).status_code == 400, settings
        assert 'shuffle' not in self.problem(self.single).data

    def test_only_containers(self):
        assert self.apply(self.single.location, {'shuffle': 'off'}).status_code == 400

    def test_needs_write_access(self):
        client, _ = self.create_non_staff_authed_user_client()
        assert self.apply(self.section.location, {'shuffle': 'per_student'}, client).status_code == 403
        assert client.get(self.url(self.section.location)).status_code == 403
        assert 'shuffle' not in self.problem(self.single).data


def test_with_shuffle_changes_only_the_group_tags():
    olx = '<problem><choicegroup  shuffle="false" type="MultipleChoice"><choice>A &amp; B</choice></choicegroup></problem>'
    assert _with_shuffle(olx, True) == (
        '<problem><choicegroup type="MultipleChoice" shuffle="true"><choice>A &amp; B</choice></choicegroup></problem>'
    )
    assert _with_shuffle(_with_shuffle(olx, True), False) == (
        '<problem><choicegroup type="MultipleChoice"><choice>A &amp; B</choice></choicegroup></problem>'
    )
