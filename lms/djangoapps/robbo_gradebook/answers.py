# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# «Ответы учащегося» in the gradebook MFE (frontend-app-gradebook, src/robbo/answers): the
# problems of one graded subsection as one learner sees them, with the learner's answers, the
# correct answers and which of them were wrong. Scores come from the grades app (the numbers
# behind the gradebook cell); capa answers are rebuilt from the learner's problem state the way
# the problem responses report does it (ProblemBlock.generate_report_data), with correctness
# from the state's correct map. Choices keep their pictures (`files`); open responses come with
# the text and the files of the last submission. Other scorable blocks (drag and drop, SCORM)
# get their score only.

"""Answers of one learner to the problems of a graded subsection, for the gradebook MFE."""

import html
import json
import logging
import mimetypes
import re
from copy import deepcopy

from django.contrib.auth import get_user_model
from django.utils.html import strip_tags
from openassessment.data import OraSubmissionAnswerFactory
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import UsageKey
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from submissions import api as submissions_api

from common.djangoapps.static_replace import replace_static_urls
from common.djangoapps.student.models import CourseEnrollment, anonymous_id_for_user
from lms.djangoapps.courseware.user_state_client import DjangoXBlockUserStateClient
from lms.djangoapps.grades.api import CourseGradeFactory
from lms.djangoapps.grades.rest_api.v1.gradebook_views import (
    course_author_access_required,
    verify_writable_gradebook_enabled,
)
from openedx.core.lib.api.view_utils import DeveloperErrorViewMixin, verify_course_exists, view_auth_classes
from xmodule.capa.capa_problem import LoncapaProblem, LoncapaSystem
from xmodule.contentstore.django import contentstore
from xmodule.modulestore.django import modulestore
from xmodule.util.sandboxing import SandboxService

log = logging.getLogger(__name__)

CORRECT = 'correct'
INCORRECT = 'incorrect'
PARTIALLY_CORRECT = 'partially-correct'
CORRECTNESS_VALUES = (CORRECT, INCORRECT, PARTIALLY_CORRECT)

# The state fields LoncapaProblem reads (as in ProblemBlock.generate_report_data).
CAPA_STATE_FIELDS = ('done', 'correct_map', 'student_answers', 'has_saved_answers', 'input_state')

CHOICE_NAME = re.compile(r'^choice_(\d+)$')

# Feedback written next to a choice for the learner, not a part of the choice.
CHOICE_HINT_TAGS = ('choicehint',)


def scorable_blocks_in_units(structure, subsection_key):
    """
    [(unit key, unit name, block key)] of the scorable blocks under the subsection in the
    learner's course structure, in outline order. Blocks inside library, split test or
    conditional blocks keep their unit; blocks outside any unit have no unit key and name.
    """
    found = []

    def visit(block_key, unit_key, unit_name):
        if structure.get_xblock_field(block_key, 'has_score', False):
            found.append((unit_key, unit_name, block_key))
            return
        if block_key.block_type == 'vertical':
            unit_key, unit_name = block_key, structure.get_xblock_field(block_key, 'display_name') or ''
        for child_key in structure.get_children(block_key):
            visit(child_key, unit_key, unit_name)

    if subsection_key in structure:
        for child_key in structure.get_children(subsection_key):
            visit(child_key, None, '')
    return found


def scorable_blocks(structure, subsection_key):
    """[(unit name, block key)] of the scorable blocks under the subsection, in outline order."""
    return [(unit_name, block_key) for _, unit_name, block_key in scorable_blocks_in_units(structure, subsection_key)]


def _loncapa_problem(block, state):
    """The learner's capa problem rebuilt from its state, as in ProblemBlock.generate_report_data."""
    capa_system = LoncapaSystem(
        ajax_url=None,
        # Anonymous ids are needed only by problems that send answers to external graders.
        anonymous_student_id=None,
        cache=None,
        can_execute_unsafe_code=lambda: False,
        get_python_lib_zip=(
            lambda: SandboxService(contentstore, block.scope_ids.usage_id.context_key).get_python_lib_zip()
        ),
        DEBUG=None,
        i18n=block.runtime.service(block, 'i18n'),
        render_template=None,
        resources_fs=block.runtime.resources_fs,
        seed=1,
        xqueue=None,
        matlab_api_key=None,
    )
    seed = state.get('seed') or 1
    return LoncapaProblem(
        problem_text=block.data,
        id=block.location.html_id(),
        capa_system=capa_system,
        capa_block=None,
        state={**{field: state.get(field) for field in CAPA_STATE_FIELDS}, 'seed': seed},
        seed=seed,
        extract_tree=False,
    )


def _choice_order(value):
    """Choices in the order of the problem (stored sets of checkbox choices have none)."""
    match = CHOICE_NAME.match(value) if isinstance(value, str) else None
    return int(match.group(1)) if match else -1


def _answer_text(lcp, answer_id, value):
    """Readable text of a stored answer: choice names become the text of the choices."""
    if value in (None, '', []):
        return ''
    if isinstance(value, (list, tuple, set)):
        value = sorted(value, key=_choice_order)
    if isinstance(value, (list, str)):
        try:
            return lcp.find_answer_text(answer_id, value)
        except NotImplementedError:  # lists of non-strings
            pass
    # Dicts and other structures of rare input types.
    return json.dumps(value, ensure_ascii=False)


def _file(url, name, image, description=''):
    """One file of an answer: a picture of a choice (named by its alt text) or an uploaded file."""
    return {'url': url, 'name': name or '', 'description': description or '', 'image': image}


def _image_url(src, course_key):
    """Course asset links (/static/...) of a picture become the URLs of the assets."""
    return replace_static_urls(f'"{src}"', course_id=course_key)[1:-1]


def _choice_content(choice, course_key):
    """Text and pictures of a choice; the hints written for the learner are left out."""
    choice = deepcopy(choice)
    for hint in choice.xpath('|'.join(f'.//{tag}' for tag in CHOICE_HINT_TAGS)):
        hint.getparent().remove(hint)
    text = ' '.join(''.join(choice.itertext()).split())
    files = [
        _file(_image_url(image.get('src'), course_key), image.get('alt', ''), True)
        for image in choice.iter('img') if image.get('src')
    ]
    return text, files


def _choices(lcp, answer_id, value):
    """The <choice> elements of the stored choice names, in problem order; None for other answers."""
    names = value if isinstance(value, (list, tuple, set)) else [value]
    if not names or not all(isinstance(name, str) and CHOICE_NAME.match(name) for name in names):
        return None
    choices = []
    for name in sorted(names, key=_choice_order):
        found = lcp.tree.xpath(f'//*[@id="{answer_id}"]//*[@name="{name}"]')
        if len(found) != 1:
            return None
        choices.append(found[0])
    return choices


def _answer_content(lcp, answer_id, value, course_key):
    """
    Readable answer and its files: chosen choices give their text and pictures (a choice can be
    a picture only); other answers give their text.
    """
    choices = _choices(lcp, answer_id, value) if value not in (None, '', []) else None
    if choices is None:
        return _answer_text(lcp, answer_id, value), []
    texts, files = [], []
    for choice in choices:
        text, images = _choice_content(choice, course_key)
        if text:
            texts.append(text)
        files.extend(images)
    return ', '.join(texts), files


def _correct_answer_content(lcp, answer_id, value, course_key):
    """Readable correct answer: numerical and text answers come with markup («<b>or</b>»)."""
    text, files = _answer_content(lcp, answer_id, value, course_key)
    return html.unescape(strip_tags(text)).strip(), files


def capa_answers(block, state):
    """
    The learner's last answer to a capa problem, one entry per input in problem order:
    [{question, answer, files, correctAnswer, correctFiles, correctness}]; [] without an answer.

    Saved but not submitted answers have no correctness: the correct map in the state is the
    one of the previous submission.
    """
    if not state.get('student_answers'):
        return []
    course_key = block.location.course_key
    lcp = _loncapa_problem(block, state)
    correct_answers = lcp.get_question_answers()
    saved = bool(state.get('has_saved_answers'))
    answers = []
    for responder in lcp.responders.values():
        for answer_id in responder.answer_ids:
            correctness = None if saved else lcp.correct_map.get_correctness(answer_id)
            answer, files = _answer_content(lcp, answer_id, lcp.student_answers.get(answer_id), course_key)
            correct_answer, correct_files = _correct_answer_content(
                lcp, answer_id, correct_answers.get(answer_id), course_key,
            )
            answers.append({
                'question': lcp.find_question_label(answer_id),
                'answer': answer,
                'files': files,
                'correctAnswer': correct_answer,
                'correctFiles': correct_files,
                'correctness': correctness if correctness in CORRECTNESS_VALUES else None,
            })
    return answers


def _prompt_text(prompt):
    """Text of an open response prompt (html prompts too)."""
    return ' '.join(html.unescape(strip_tags(prompt.get('description') or '')).split())


def ora_submission(block, learner):
    """The learner's last open response submission (None without one); team ones are not read."""
    if getattr(block, 'teams_enabled', False):
        return None
    submissions = submissions_api.get_submissions({
        'student_id': anonymous_id_for_user(learner, block.location.course_key),
        'course_id': str(block.location.course_key),
        'item_id': str(block.location),
        'item_type': block.location.block_type,
    }, limit=1)
    return submissions[0] if submissions else None


def ora_answers(block, submission):
    """
    The text of an open response submission, one entry per prompt, the files with the last one:
    [{question, answer, files, correctAnswer: '', correctFiles: [], correctness: None}].
    File links are the ones of the upload backend: they work for a while (ORA gives them so too).
    """
    if submission is None:
        return []
    answer = OraSubmissionAnswerFactory.parse_submission_raw_answer(submission.get('answer'))
    texts = answer.get_text_responses()
    prompts = block.prompts or []
    files = [
        _file(upload.url, upload.name, _is_image(upload.name), upload.description)
        for upload in answer.get_file_uploads(missing_blank=True, generate_urls=True) if upload.url
    ]
    entries = [
        {
            'question': _prompt_text(prompts[index]) if index < len(prompts) else '',
            'answer': (text or '').strip(),
            'files': [],
            'correctAnswer': '',
            'correctFiles': [],
            'correctness': None,
        }
        for index, text in enumerate(texts)
    ]
    if files:
        if not entries:
            entries.append({
                'question': _prompt_text(prompts[0]) if prompts else '', 'answer': '', 'files': [],
                'correctAnswer': '', 'correctFiles': [], 'correctness': None,
            })
        entries[-1]['files'] = files
    return entries


def _is_image(name):
    """Pictures among the uploaded files, by their names."""
    content_type, _ = mimetypes.guess_type(name or '')
    return bool(content_type and content_type.startswith('image/'))


def _score_correctness(score):
    """Correctness of a scored attempt by its points; None when nothing was graded."""
    if score is None or not score.possible:
        return None
    if score.earned >= score.possible:
        return CORRECT
    return PARTIALLY_CORRECT if score.earned > 0 else INCORRECT


def _answers_correctness(answers):
    """Correctness of a problem without points (weight 0) by the correctness of its inputs."""
    values = {answer['correctness'] for answer in answers} - {None}
    if not values:
        return None
    if values == {CORRECT}:
        return CORRECT
    return INCORRECT if values == {INCORRECT} else PARTIALLY_CORRECT


def _problem_entry(block, unit_name, score, state, learner):
    """One problem of the subsection with the learner's score and answers (see the view)."""
    entry = {
        'id': str(block.location),
        'type': block.location.block_type,
        'name': block.display_name_with_default,
        'unitName': unit_name,
        'earned': score.earned if score else None,
        'possible': score.possible if score else None,
        'graded': bool(score and score.graded),
        'attempts': state.get('attempts') or 0,
        'saved': bool(state.get('has_saved_answers')),
        'answers': None,
        'answersError': False,
        'awaitingGrade': False,
    }
    if entry['type'] == 'problem':
        try:
            entry['answers'] = capa_answers(block, state)
        except Exception:  # pylint: disable=broad-except
            # Broken XML or a failing script must not hide the other problems.
            log.exception('Robbo gradebook: cannot read the answers to %s', block.location)
            entry['answers'] = []
            entry['answersError'] = True
        # A submission leaves a correct map; saving answers or opening the problem does not.
        submitted = bool(state.get('correct_map'))
    elif entry['type'] == 'openassessment':
        try:
            submission = ora_submission(block, learner)
            entry['answers'] = ora_answers(block, submission)
        except Exception:  # pylint: disable=broad-except
            log.exception('Robbo gradebook: cannot read the response to %s', block.location)
            submission = None
            entry['answers'] = []
            entry['answersError'] = True
        submitted = bool(score and score.first_attempted)
        # Submitted, the score comes after the assessments.
        entry['awaitingGrade'] = bool(submission) and not submitted
    else:
        submitted = bool(score and score.first_attempted)

    if not submitted:
        entry['correctness'] = None
    elif score is not None and score.possible:
        entry['correctness'] = _score_correctness(score)
    else:
        entry['correctness'] = _answers_correctness(entry['answers'] or [])
    return entry


def learner_subsection_answers(course_key, learner, subsection_key):
    """The learner's scorable blocks of the subsection with scores and answers, in outline order."""
    course_grade = CourseGradeFactory().read(learner, course_key=course_key)
    structure = course_grade.course_data.structure
    blocks = scorable_blocks(structure, subsection_key)
    if not blocks:
        return []
    scores = course_grade.subsection_grade(subsection_key).problem_scores
    states = {
        user_state.block_key: user_state.state
        for user_state in DjangoXBlockUserStateClient().get_many(learner.username, [key for _, key in blocks])
    }
    store = modulestore()
    with store.bulk_operations(course_key):
        return [
            _problem_entry(
                store.get_item(block_key), unit_name, scores.get(block_key), states.get(block_key, {}), learner,
            )
            for unit_name, block_key in blocks
        ]


@view_auth_classes()
class LearnerAnswersView(DeveloperErrorViewMixin, APIView):
    """
    **Use Case**
        The problems of a graded subsection with one learner's answers: what the course team sees
        after clicking a grade in the gradebook MFE. Same access as the gradebook API.

    **Example Request**
        GET /api/robbo/v1/gradebook/{course_id}/answers/?user_id={user_id}&subsection={usage_key}

    **Response Values**
        problems: the scorable blocks the learner sees in the subsection, in outline order:
            id, type (block type), name, unitName,
            earned, possible: weighted points as in the grade (null without a score),
            graded: whether the points count in the grade,
            attempts: submissions of a capa problem,
            saved: the learner saved answers without submitting them,
            correctness: correct | incorrect | partially-correct of the last submission, null when
                nothing was submitted,
            answers: capa problems (one per input) and open responses (one per prompt), null
                for other blocks, [] without an answer:
                [{question, answer, files, correctAnswer, correctFiles, correctness}];
                files, correctFiles: [{url, name, description, image}] — pictures of the choices
                (name: alt text), files of an open response (urls may be relative to the LMS),
            answersError: the problem could not be read (answers are then []),
            awaitingGrade: an open response was submitted and is not graded yet.

    Only learners of this course (enrolled now or before): other user ids get the same 404 as
    unknown ones.
    """

    @verify_course_exists("Requested answers for unknown course {course}")
    @verify_writable_gradebook_enabled
    @course_author_access_required
    def get(self, request, course_key):
        """Answers of the learner `user_id` in the subsection `subsection`."""
        try:
            learner_id = int(request.GET.get('user_id', ''))
            subsection_key = UsageKey.from_string(request.GET.get('subsection', ''))
        except (ValueError, InvalidKeyError) as error:
            raise self.api_error(
                status_code=status.HTTP_400_BAD_REQUEST,
                developer_message='user_id and subsection (a usage key) are required.',
                error_code='invalid_parameters',
            ) from error

        if subsection_key.context_key != course_key or subsection_key.block_type != 'sequential':
            raise self.api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                developer_message='The subsection is not in this course.',
                error_code='unknown_subsection',
            )
        learner = get_user_model().objects.filter(id=learner_id).first()
        if learner is None or not CourseEnrollment.objects.filter(user=learner, course_id=course_key).exists():
            raise self.api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                developer_message='The learner is not in this course.',
                error_code='unknown_learner',
            )

        return Response({'problems': learner_subsection_answers(course_key, learner, subsection_key)})
