"""Tests the capa shuffle and name-masking."""


import textwrap
import unittest

from xmodule.capa.responsetypes import LoncapaProblemError
from xmodule.capa.tests.helpers import new_loncapa_problem, test_capa_system


class CapaShuffleTest(unittest.TestCase):
    """Capa problem tests for shuffling and choice-name masking."""

    def setUp(self):
        super(CapaShuffleTest, self).setUp()  # lint-amnesty, pylint: disable=super-with-arguments
        self.system = test_capa_system()

    def test_shuffle_4_choices(self):
        xml_str = textwrap.dedent("""
            <problem>
            <multiplechoiceresponse>
              <choicegroup type="MultipleChoice" shuffle="true">
                <choice correct="false">Apple</choice>
                <choice correct="false">Banana</choice>
                <choice correct="false">Chocolate</choice>
                <choice correct ="true">Donut</choice>
              </choicegroup>
            </multiplechoiceresponse>
            </problem>
        """)
        problem = new_loncapa_problem(xml_str, seed=0)
        # shuffling 4 things with seed of 0 yields: B A C D
        # Check that the choices are shuffled
        the_html = problem.get_html()
        self.assertRegex(the_html, r"<div>.*\[.*'Banana'.*'Apple'.*'Chocolate'.*'Donut'.*\].*</div>")
        # Check that choice name masking is enabled and that unmasking works
        response = list(problem.responders.values())[0]
        assert not response.has_mask()
        assert response.unmask_order() == ['choice_1', 'choice_0', 'choice_2', 'choice_3']
        assert the_html == problem.get_html(), 'should be able to call get_html() twice'

    def test_shuffle_custom_names(self):
        xml_str = textwrap.dedent("""
            <problem>
            <multiplechoiceresponse>
              <choicegroup type="MultipleChoice" shuffle="true">
                <choice correct="false" name="aaa">Apple</choice>
                <choice correct="false">Banana</choice>
                <choice correct="false">Chocolate</choice>
                <choice correct ="true" name="ddd">Donut</choice>
              </choicegroup>
            </multiplechoiceresponse>
            </problem>
        """)
        problem = new_loncapa_problem(xml_str, seed=0)
        # B A C D
        # Check that the custom name= names come through
        response = list(problem.responders.values())[0]
        assert not response.has_mask()
        assert response.has_shuffle()
        assert response.unmask_order() == ['choice_0', 'choice_aaa', 'choice_1', 'choice_ddd']

    def test_shuffle_different_seed(self):
        xml_str = textwrap.dedent("""
            <problem>
            <multiplechoiceresponse>
              <choicegroup type="MultipleChoice" shuffle="true">
                <choice correct="false">Apple</choice>
                <choice correct="false">Banana</choice>
                <choice correct="false">Chocolate</choice>
                <choice correct ="true">Donut</choice>
              </choicegroup>
            </multiplechoiceresponse>
            </problem>
        """)
        problem = new_loncapa_problem(xml_str, seed=341)  # yields D A B C
        the_html = problem.get_html()
        self.assertRegex(the_html, r"<div>.*\[.*'Donut'.*'Apple'.*'Banana'.*'Chocolate'.*\].*</div>")

    def test_shuffle_1_choice(self):
        xml_str = textwrap.dedent("""
            <problem>
            <multiplechoiceresponse>
              <choicegroup type="MultipleChoice" shuffle="true">
                <choice correct="true">Apple</choice>
              </choicegroup>
            </multiplechoiceresponse>
            </problem>
        """)
        problem = new_loncapa_problem(xml_str, seed=0)
        the_html = problem.get_html()
        self.assertRegex(the_html, r"<div>.*\[.*'Apple'.*\].*</div>")
        response = list(problem.responders.values())[0]
        assert not response.has_mask()
        assert response.has_shuffle()
        assert response.unmask_order() == ['choice_0']

    def test_shuffle_6_choices(self):
        xml_str = textwrap.dedent("""
            <problem>
            <multiplechoiceresponse>
              <choicegroup type="MultipleChoice" shuffle="true">
                <choice correct="false">Apple</choice>
                <choice correct="false">Banana</choice>
                <choice correct="false">Chocolate</choice>
                <choice correct ="true">Zonut</choice>
                <choice correct ="false">Eggplant</choice>
                <choice correct ="false">Filet Mignon</choice>
              </choicegroup>
            </multiplechoiceresponse>
            </problem>
        """)
        problem = new_loncapa_problem(xml_str, seed=0)  # yields: C E A B D F
        # Donut -> Zonut to show that there is not some hidden alphabetic ordering going on
        the_html = problem.get_html()
        self.assertRegex(the_html, r"<div>.*\[.*'Chocolate'.*'Eggplant'.*'Apple'.*'Banana'.*'Zonut'.*'Filet Mignon'.*\].*</div>")  # lint-amnesty, pylint: disable=line-too-long

    def test_shuffle_false(self):
        xml_str = textwrap.dedent("""
            <problem>
            <multiplechoiceresponse>
              <choicegroup type="MultipleChoice" shuffle="false">
                <choice correct="false">Apple</choice>
                <choice correct="false">Banana</choice>
                <choice correct="false">Chocolate</choice>
                <choice correct ="true">Donut</choice>
              </choicegroup>
            </multiplechoiceresponse>
            </problem>
        """)
        problem = new_loncapa_problem(xml_str)
        the_html = problem.get_html()
        self.assertRegex(the_html, r"<div>.*\[.*'Apple'.*'Banana'.*'Chocolate'.*'Donut'.*\].*</div>")
        response = list(problem.responders.values())[0]
        assert not response.has_mask()
        assert not response.has_shuffle()

    def test_shuffle_fixed_head_end(self):
        xml_str = textwrap.dedent("""
            <problem>
            <multiplechoiceresponse>
              <choicegroup type="MultipleChoice" shuffle="true">
                <choice correct="false" fixed="true">Alpha</choice>
                <choice correct="false" fixed="true">Beta</choice>
                <choice correct="false">A</choice>
                <choice correct="false">B</choice>
                <choice correct="false">C</choice>
                <choice correct ="true">D</choice>
              </choicegroup>
            </multiplechoiceresponse>
            </problem>
        """)
        problem = new_loncapa_problem(xml_str, seed=0)
        the_html = problem.get_html()
        # Alpha Beta held back from shuffle (head end)
        self.assertRegex(the_html, r"<div>.*\[.*'Alpha'.*'Beta'.*'B'.*'A'.*'C'.*'D'.*\].*</div>")

    def test_shuffle_fixed_tail_end(self):
        xml_str = textwrap.dedent("""
            <problem>
            <multiplechoiceresponse>
              <choicegroup type="MultipleChoice" shuffle="true">
                <choice correct="false">A</choice>
                <choice correct="false">B</choice>
                <choice correct="false">C</choice>
                <choice correct ="true">D</choice>
                <choice correct="false" fixed="true">Alpha</choice>
                <choice correct="false" fixed="true">Beta</choice>
              </choicegroup>
            </multiplechoiceresponse>
            </problem>
        """)
        problem = new_loncapa_problem(xml_str, seed=0)
        the_html = problem.get_html()
        # Alpha Beta held back from shuffle (tail end)
        self.assertRegex(the_html, r"<div>.*\[.*'B'.*'A'.*'C'.*'D'.*'Alpha'.*'Beta'.*\].*</div>")

    def test_shuffle_fixed_both_ends(self):
        xml_str = textwrap.dedent("""
            <problem>
            <multiplechoiceresponse>
              <choicegroup type="MultipleChoice" shuffle="true">
                <choice correct="false" fixed="true">Alpha</choice>
                <choice correct="false" fixed="true">Beta</choice>
                <choice correct="false">A</choice>
                <choice correct="false">B</choice>
                <choice correct="false">C</choice>
                <choice correct ="true">D</choice>
                <choice correct="false" fixed="true">Psi</choice>
                <choice correct="false" fixed="true">Omega</choice>

              </choicegroup>
            </multiplechoiceresponse>
            </problem>
        """)
        problem = new_loncapa_problem(xml_str, seed=0)
        the_html = problem.get_html()
        self.assertRegex(
            the_html,
            r"<div>.*\[.*'Alpha'.*'Beta'.*'B'.*'A'.*'C'.*'D'.*'Psi'.*'Omega'.*\].*</div>"
        )

    def test_shuffle_fixed_both_ends_thin(self):
        xml_str = textwrap.dedent("""
            <problem>
            <multiplechoiceresponse>
              <choicegroup type="MultipleChoice" shuffle="true">
                <choice correct="false" fixed="true">Alpha</choice>
                <choice correct="false">A</choice>
                <choice correct="true" fixed="true">Omega</choice>
              </choicegroup>
            </multiplechoiceresponse>
            </problem>
        """)
        problem = new_loncapa_problem(xml_str, seed=0)
        the_html = problem.get_html()
        self.assertRegex(the_html, r"<div>.*\[.*'Alpha'.*'A'.*'Omega'.*\].*</div>")

    def test_shuffle_fixed_all(self):
        xml_str = textwrap.dedent("""
            <problem>
            <multiplechoiceresponse>
              <choicegroup type="MultipleChoice" shuffle="true">
                <choice correct="false" fixed="true">A</choice>
                <choice correct="false" fixed="true">B</choice>
                <choice correct="true" fixed="true">C</choice>
              </choicegroup>
            </multiplechoiceresponse>
            </problem>
        """)
        problem = new_loncapa_problem(xml_str, seed=0)
        the_html = problem.get_html()
        self.assertRegex(the_html, r"<div>.*\[.*'A'.*'B'.*'C'.*\].*</div>")

    def test_shuffle_island(self):
        """A fixed 'island' choice not at the head or tail end gets lumped into the tail end."""
        xml_str = textwrap.dedent("""
            <problem>
            <multiplechoiceresponse>
              <choicegroup type="MultipleChoice" shuffle="true">
                <choice correct="false" fixed="true">A</choice>
                <choice correct="false">Mid</choice>
                <choice correct="true" fixed="true">C</choice>
                <choice correct="False">Mid</choice>
                <choice correct="false" fixed="true">D</choice>
              </choicegroup>
            </multiplechoiceresponse>
            </problem>
        """)
        problem = new_loncapa_problem(xml_str, seed=0)
        the_html = problem.get_html()
        self.assertRegex(the_html, r"<div>.*\[.*'A'.*'Mid'.*'Mid'.*'C'.*'D'.*\].*</div>")

    def test_multiple_shuffle_responses(self):
        xml_str = textwrap.dedent("""
            <problem>
            <multiplechoiceresponse>
              <choicegroup type="MultipleChoice" shuffle="true">
                <choice correct="false">Apple</choice>
                <choice correct="false">Banana</choice>
                <choice correct="false">Chocolate</choice>
                <choice correct ="true">Donut</choice>
              </choicegroup>
            </multiplechoiceresponse>
            <p>Here is some text</p>
            <multiplechoiceresponse>
              <choicegroup type="MultipleChoice" shuffle="true">
                <choice correct="false">A</choice>
                <choice correct="false">B</choice>
                <choice correct="false">C</choice>
                <choice correct ="true">D</choice>
              </choicegroup>
            </multiplechoiceresponse>
            </problem>
        """)
        problem = new_loncapa_problem(xml_str, seed=0)
        orig_html = problem.get_html()
        assert orig_html == problem.get_html(), 'should be able to call get_html() twice'
        html = orig_html.replace('\n', ' ')  # avoid headaches with .* matching
        print(html)
        self.assertRegex(html, r"<div>.*\[.*'Banana'.*'Apple'.*'Chocolate'.*'Donut'.*\].*</div>.*" +
                         r"<div>.*\[.*'C'.*'A'.*'D'.*'B'.*\].*</div>")
        # Look at the responses in their authored order
        responses = sorted(list(problem.responders.values()), key=lambda resp: int(resp.id[resp.id.rindex('_') + 1:]))
        assert not responses[0].has_mask()
        assert responses[0].has_shuffle()
        assert responses[1].has_shuffle()
        assert responses[0].unmask_order() == ['choice_1', 'choice_0', 'choice_2', 'choice_3']
        assert responses[1].unmask_order() == ['choice_2', 'choice_0', 'choice_3', 'choice_1']

    def test_shuffle_not_with_answerpool(self):
        """Raise error if shuffle and answer-pool are both used."""
        xml_str = textwrap.dedent("""
            <problem>
            <multiplechoiceresponse>
              <choicegroup type="MultipleChoice" shuffle="true" answer-pool="4">
                <choice correct="false" fixed="true">A</choice>
                <choice correct="false">Mid</choice>
                <choice correct="true" fixed="true">C</choice>
                <choice correct="False">Mid</choice>
                <choice correct="false" fixed="true">D</choice>
              </choicegroup>
            </multiplechoiceresponse>
            </problem>
        """)

        with self.assertRaisesRegex(LoncapaProblemError, "shuffle and answer-pool"):
            new_loncapa_problem(xml_str)

    def test_shuffle_checkboxgroup(self):
        """Robbo: shuffle="true" on <checkboxgroup> shuffles like <choicegroup>; names keep the authored order."""
        xml_str = textwrap.dedent("""
            <problem>
            <choiceresponse>
              <checkboxgroup shuffle="true">
                <choice correct="false">Apple</choice>
                <choice correct="true">Banana</choice>
                <choice correct="false">Chocolate</choice>
                <choice correct="true">Donut</choice>
              </checkboxgroup>
            </choiceresponse>
            </problem>
        """)
        problem = new_loncapa_problem(xml_str, seed=0)
        # Same rng as the multiple choice tests: 4 things with seed 0 yield B A C D
        response = list(problem.responders.values())[0]
        assert response.has_shuffle()
        assert response.unmask_order() == ['choice_1', 'choice_0', 'choice_2', 'choice_3']
        the_html = problem.get_html()
        self.assertRegex(the_html.replace('\n', ' '), r"Banana.*Apple.*Chocolate.*Donut")
        assert the_html == problem.get_html(), 'should be able to call get_html() twice'
        correct_map = problem.grade_answers({response.answer_id: ['choice_1', 'choice_3']})
        assert correct_map.get_correctness(response.answer_id) == 'correct'

    def test_shuffle_checkboxgroup_fixed_and_compoundhint(self):
        """Robbo: fixed choices stay at the tail, <compoundhint> keeps its place and still matches by id."""
        xml_str = textwrap.dedent("""
            <problem>
            <choiceresponse>
              <checkboxgroup shuffle="true">
                <choice correct="true">Apple</choice>
                <choice correct="false">Banana</choice>
                <choice correct="true">Chocolate</choice>
                <choice correct="false" fixed="true">None of the above</choice>
                <compoundhint value="A B">Apple and Banana</compoundhint>
              </checkboxgroup>
            </choiceresponse>
            </problem>
        """)
        problem = new_loncapa_problem(xml_str, seed=0)
        response = list(problem.responders.values())[0]
        assert response.unmask_order()[-1] == 'choice_3'
        group = response.xml.find('checkboxgroup')
        assert group[-1].tag == 'compoundhint'
        correct_map = problem.grade_answers({response.answer_id: ['choice_0', 'choice_1']})
        assert 'Apple and Banana' in correct_map.get_msg(response.answer_id)

    def test_no_shuffle_checkboxgroup(self):
        """Robbo: without shuffle="true" checkboxes keep the authored order."""
        xml_str = textwrap.dedent("""
            <problem>
            <choiceresponse>
              <checkboxgroup>
                <choice correct="false">Apple</choice>
                <choice correct="true">Banana</choice>
                <choice correct="false">Chocolate</choice>
              </checkboxgroup>
            </choiceresponse>
            </problem>
        """)
        problem = new_loncapa_problem(xml_str, seed=0)
        response = list(problem.responders.values())[0]
        assert not response.has_shuffle()
        assert response.unmask_order() == ['choice_0', 'choice_1', 'choice_2']
