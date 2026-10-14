# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# «Проверка по учащимся» in the ORA grading MFE (frontend-app-ora-grading, src/robbo/learners):
# all open response assignments of a course, the answers of one learner at a time. Lists and
# statuses are read from the edx-ora2 staff grading tables for the whole course in a few
# queries (the stock ESG reads them one assignment at a time through the XBlock); locking and
# grading go through the stock ESG endpoints (lms/djangoapps/ora_staff_grader) with the
# assignment of the answer.

"""Course-wide, per-learner view of open response answers for the ORA grading MFE."""

import logging

from django.contrib.auth import get_user_model
from django.db.models import Case, CharField, OuterRef, Prefetch, Subquery, Value, When
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from openassessment.assessment.models.base import Assessment, AssessmentPart
from openassessment.assessment.models.staff import StaffWorkflow
from openassessment.data import (
    OraSubmissionAnswerFactory,
    VersionNotFoundException,
    map_anonymized_ids_to_user_data,
)
from openassessment.staffgrader.models.submission_lock import SubmissionGradingLock
from openassessment.staffgrader.serializers import SubmissionDetailFileSerilaizer, SubmissionListSerializer
from rest_framework import status
from rest_framework.response import Response
from submissions.api import get_student_ids_by_submission_uuid, get_submission
from submissions.errors import SubmissionError
from submissions.models import Submission
from xmodule.modulestore.django import modulestore

from common.djangoapps.student.models import AnonymousUserId, CourseEnrollment, anonymous_id_for_user
from lms.djangoapps.courseware.access import has_access
from lms.djangoapps.ora_staff_grader.serializers import (
    CourseMetadataSerializer,
    OpenResponseMetadataSerializer,
    ResponseSerializer,
    SubmissionMetadataSerializer,
)
from lms.djangoapps.ora_staff_grader.views import InitializeView, StaffGraderBaseView
from openedx.core.djangoapps.content.course_overviews.api import get_course_overview_or_none

log = logging.getLogger(__name__)


def course_oras(course_key):
    """
    Individual open response assignments of the course in outline order: (unit name, block).

    Team assignments are left out: the stock grading tool does not grade them either.
    Assignments outside the section/subsection/unit tree (rare) go last.
    """
    store = modulestore()
    course = store.get_course(course_key, depth=3)
    position, unit_names = {}, {}
    for chapter in course.get_children():
        for sequential in chapter.get_children():
            for unit in sequential.get_children():
                for child in unit.children:
                    key = str(child.map_into_course(course_key))
                    position[key] = len(position)
                    unit_names[key] = unit.display_name_with_default

    blocks = [
        block for block in store.get_items(course_key, qualifiers={'category': 'openassessment'})
        if not block.teams_enabled
    ]
    blocks.sort(key=lambda block: position.get(str(block.location), len(position)))
    return [(unit_names.get(str(block.location), ''), block) for block in blocks]


def _latest_per_learner_and_item(rows, student_ids, user_data):
    """
    {(username, item_id): row} with the newest non-cancelled workflow of each pair.

    A learner can have several anonymous ids in a course and, after a reset, several
    submissions of one assignment; the newest one is what the learner sees.
    """
    latest = {}
    for row in rows:
        learner = user_data.get(student_ids.get(row['submission_uuid']))
        if not learner:
            continue
        key = (learner['username'], row['item_id'])
        if key not in latest or row['created_at'] > latest[key]['created_at']:
            latest[key] = row
    return latest


def learners_summary(course_key, item_ids):
    """Learners with at least one answer: how many answers they sent and how many wait for a grade."""
    course_id = str(course_key)
    rows = list(
        StaffWorkflow.objects.filter(course_id=course_id, item_id__in=item_ids, cancelled_at=None)
        .values('submission_uuid', 'item_id', 'assessment', 'created_at')
    )
    student_ids = get_student_ids_by_submission_uuid(
        course_id, [row['submission_uuid'] for row in rows], read_replica=False,
    )
    user_data = map_anonymized_ids_to_user_data(set(student_ids.values()))

    learners = {}
    latest = _latest_per_learner_and_item(rows, student_ids, user_data)
    for row in latest.values():
        data = user_data[student_ids[row['submission_uuid']]]
        entry = learners.setdefault(data['username'], {
            'username': data['username'],
            'fullname': data['fullname'],
            'email': data['email'],
            'submitted': 0,
            'ungraded': 0,
        })
        entry['submitted'] += 1
        if not row['assessment']:
            entry['ungraded'] += 1

    return sorted(
        learners.values(),
        key=lambda entry: (entry['ungraded'] == 0, (entry['fullname'] or entry['username']).lower()),
    )


def _annotated_workflows(course_key, grader, submission_uuids):
    """
    StaffWorkflows of the given submissions with the grading and lock statuses of the stock
    ESG list (edx-ora2 StaffGraderMixin._bulk_fetch_annotated_staff_workflows), course-wide.
    """
    newest_lock = SubmissionGradingLock.currently_active().filter(
        submission_uuid=OuterRef('submission_uuid'),
    ).order_by('-created_at')
    return StaffWorkflow.objects.filter(
        course_id=str(course_key),
        submission_uuid__in=submission_uuids,
        cancelled_at=None,
    ).annotate(
        current_lock_user=Subquery(newest_lock.values('owner_id')),
    ).annotate(
        grading_status=Case(
            When(assessment__isnull=False, then=Value('graded')),
            default=Value('ungraded'),
            output_field=CharField(),
        ),
        lock_status=Case(
            When(current_lock_user=anonymous_id_for_user(grader, course_key), then=Value('in-progress')),
            When(current_lock_user__isnull=False, then=Value('locked')),
            default=Value('unlocked'),
            output_field=CharField(),
        ),
    )


def _assessments_by_submission(workflows):
    """Staff assessments of the workflows with their rubric parts (as the stock ESG list fetches them)."""
    uuid_by_assessment = {wf.assessment: wf.submission_uuid for wf in workflows if wf.assessment}
    assessments = Assessment.objects.filter(pk__in=uuid_by_assessment.keys()).prefetch_related(
        Prefetch('parts', queryset=AssessmentPart.objects.select_related('criterion', 'option')),
        'rubric__criteria',
        'rubric__criteria__options',
    ).select_related('rubric')
    return {uuid_by_assessment[str(assessment.id)]: assessment for assessment in assessments}


def _response(submission_uuid):
    """Text and files of the answer, in the shape of the stock ESG submission response."""
    try:
        answer = OraSubmissionAnswerFactory.parse_submission_raw_answer(get_submission(submission_uuid)['answer'])
        files = [SubmissionDetailFileSerilaizer(upload).data for upload in answer.get_file_uploads(generate_urls=True)]
        text = answer.get_text_responses()
    except (SubmissionError, VersionNotFoundException):
        log.exception('Robbo ORA grading: cannot read submission %s', submission_uuid)
        files, text = [], []
    return ResponseSerializer({'files': files, 'text': [part or '' for part in text]}).data


def learner_answers(course_key, grader, learner, item_ids):
    """{item_id: {'submission': ESG list entry, 'response': text and files}} for one learner."""
    course_id = str(course_key)
    anonymous_ids = set(
        AnonymousUserId.objects.filter(user=learner, course_id=course_key)
        .values_list('anonymous_user_id', flat=True)
    )
    if not anonymous_ids:
        return {}
    submission_uuids = [
        str(uuid) for uuid in Submission.objects.filter(
            student_item__course_id=course_id,
            student_item__student_id__in=anonymous_ids,
            student_item__item_id__in=item_ids,
        ).values_list('uuid', flat=True)
    ]
    workflows = {wf.submission_uuid: wf for wf in _annotated_workflows(course_key, grader, submission_uuids)}

    student_ids = get_student_ids_by_submission_uuid(course_id, list(workflows), read_replica=False)
    scorer_ids = {wf.scorer_id for wf in workflows.values() if wf.scorer_id}
    # Scorers that are not users (the «Засчитывать сразу после отправки» grade, scorer
    # `robbo-auto-score`) get no grader, as in the stock list: see robbo_ora_limits
    # `_patch_ora_staff_list_unknown_scorer`.
    user_data = map_anonymized_ids_to_user_data(set(student_ids.values()) | scorer_ids)
    rows = [
        {'submission_uuid': uuid, 'item_id': wf.item_id, 'created_at': wf.created_at}
        for uuid, wf in workflows.items()
    ]
    latest = [workflows[row['submission_uuid']] for row in
              _latest_per_learner_and_item(rows, student_ids, user_data).values()]

    context = {
        SubmissionListSerializer.CONTEXT_ANON_ID_TO_USERNAME: {
            anon: data['username'] for anon, data in user_data.items()
        },
        SubmissionListSerializer.CONTEXT_ANON_ID_TO_EMAIL: {anon: data['email'] for anon, data in user_data.items()},
        SubmissionListSerializer.CONTEXT_ANON_ID_TO_FULLNAME: {
            anon: data['fullname'] for anon, data in user_data.items()
        },
        SubmissionListSerializer.CONTEXT_SUB_TO_ASSESSMENT: _assessments_by_submission(latest),
        SubmissionListSerializer.CONTEXT_SUB_TO_ANON_ID: student_ids,
    }
    return {
        wf.item_id: {
            'submission': SubmissionMetadataSerializer(SubmissionListSerializer(wf, context=context).data).data,
            'response': _response(wf.submission_uuid),
        }
        for wf in latest
    }


class _CourseStaffView(StaffGraderBaseView):
    """Course team only, as the ORA staff grading handlers (`require_course_staff`)."""

    def course_key_or_error(self, request, course_id):
        """(course_key, None) or (None, error response)."""
        try:
            course_key = CourseKey.from_string(course_id)
        except InvalidKeyError:
            return None, Response({'error': 'unknown course'}, status=status.HTTP_404_NOT_FOUND)
        if not has_access(request.user, 'staff', course_key):
            return None, Response({'error': 'course team only'}, status=status.HTTP_403_FORBIDDEN)
        return course_key, None


class CourseLearnersView(_CourseStaffView):
    """
    GET the course, its open response assignments and the learners who answered them.

    Response: {
        courseMetadata: same as the stock ESG initialize,
        isEnabled: the stock ESG flag (off: demo mode, grading disabled),
        oras: [{id, unitName, oraMetadata (same as the stock ESG initialize)}] in outline order,
        learners: [{username, fullname, email, submitted, ungraded}], waiting for a grade first,
    }
    """

    def get(self, request, course_id, *args, **kwargs):
        course_key, error = self.course_key_or_error(request, course_id)
        if error:
            return error
        overview = get_course_overview_or_none(course_key)
        if overview is None:
            return Response({'error': 'unknown course'}, status=status.HTTP_404_NOT_FOUND)

        oras = course_oras(course_key)
        return Response({
            'courseMetadata': CourseMetadataSerializer(overview).data,
            # pylint: disable=protected-access
            'isEnabled': InitializeView()._is_staff_grader_enabled(course_key),
            'oras': [
                {
                    'id': str(block.location),
                    'unitName': unit_name,
                    'oraMetadata': OpenResponseMetadataSerializer(block).data,
                }
                for unit_name, block in oras
            ],
            'learners': learners_summary(course_key, [str(block.location) for _, block in oras]),
        })


class LearnerAnswersView(_CourseStaffView):
    """
    GET the answers of one learner to the course's open response assignments.

    Response: {
        learner: {username, fullname, email},
        answers: {<ora id>: {submission: stock ESG list entry, response: {text, files}}},
    }
    Assignments without an answer are not in `answers`.

    Only learners of this course (enrolled now or before, or with answers in it): the course
    team must not look up the name and email of any account. Other usernames get the same
    404 as unknown ones.
    """

    def get(self, request, course_id, username, *args, **kwargs):
        course_key, error = self.course_key_or_error(request, course_id)
        if error:
            return error
        not_found = Response({'error': 'unknown learner'}, status=status.HTTP_404_NOT_FOUND)
        learner = get_user_model().objects.filter(username=username).select_related('profile').first()
        if learner is None:
            return not_found

        item_ids = [str(block.location) for _, block in course_oras(course_key)]
        answers = learner_answers(course_key, request.user, learner, item_ids)
        if not answers and not CourseEnrollment.objects.filter(user=learner, course_id=course_key).exists():
            return not_found

        profile = getattr(learner, 'profile', None)
        return Response({
            'learner': {
                'username': learner.username,
                'fullname': profile.name if profile else '',
                'email': learner.email,
            },
            'answers': answers,
        })
