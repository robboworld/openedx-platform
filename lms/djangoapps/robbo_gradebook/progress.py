# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Progress report of the gradebook MFE (frontend-app-gradebook, src/robbo/export/report): the
# learners of a course by their last activity, to pick whom the PDF is made for, and one learner's
# course as sections → subsections → units with the points of the unit's scorable blocks. Points
# come from the grades app, the same as the gradebook cells; a unit counts as passed with all of
# its points only.

"""Learners by last activity and one learner's progress by unit, for the gradebook PDF report."""

from django.contrib.auth import get_user_model
from django.db.models import Max
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from common.djangoapps.student.models import CourseEnrollment
from lms.djangoapps.courseware.models import StudentModule
from lms.djangoapps.grades.api import CourseGradeFactory
from lms.djangoapps.grades.rest_api.v1.gradebook_views import (
    course_author_access_required,
    verify_writable_gradebook_enabled,
)
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from openedx.core.lib.api.view_utils import DeveloperErrorViewMixin, verify_course_exists, view_auth_classes

from .answers import scorable_blocks_in_units


def _full_name(user):
    """Full name of the profile, else the name parts of the account."""
    profile = getattr(user, 'profile', None)
    return (profile.name if profile and profile.name else user.get_full_name()) or ''


def course_name(course_key):
    """The course name as learners see it; the id only when the course has no overview."""
    try:
        return CourseOverview.get_from_id(course_key).display_name_with_default
    except CourseOverview.DoesNotExist:
        return str(course_key)


def course_learners(course_key):
    """
    Learners enrolled in the course now, most recently active first, the never active ones last
    (by username). Activity is the last change of the learner's state in the course: an opened
    subsection, an answer, a submission.
    """
    enrollments = CourseEnrollment.objects.filter(course_id=course_key, is_active=True).select_related(
        'user', 'user__profile',
    )
    last_activity = dict(
        StudentModule.objects.filter(course_id=course_key)
        .values('student_id').annotate(last=Max('modified')).values_list('student_id', 'last')
    )
    learners = [
        {
            'id': enrollment.user.id,
            'username': enrollment.user.username,
            'fullName': _full_name(enrollment.user),
            'email': enrollment.user.email,
            'lastActivity': last_activity.get(enrollment.user.id),
        }
        for enrollment in enrollments
    ]
    learners.sort(key=lambda learner: learner['username'].lower())
    learners.sort(key=lambda learner: learner['lastActivity'].timestamp() if learner['lastActivity'] else 0,
                  reverse=True)
    for learner in learners:
        if learner['lastActivity']:
            learner['lastActivity'] = learner['lastActivity'].isoformat()
    return learners


def _total(score):
    """{earned, possible} of an aggregated score."""
    return {'earned': score.earned, 'possible': score.possible}


def _units(structure, subsection_grade):
    """Units of the subsection with the summed points of their scorable blocks; no units without points."""
    units = {}
    for unit_key, unit_name, block_key in scorable_blocks_in_units(structure, subsection_grade.location):
        score = subsection_grade.problem_scores.get(block_key)
        if score is None:
            continue
        unit = units.setdefault(unit_key, {'name': unit_name, 'earned': 0.0, 'possible': 0.0})
        unit['earned'] += score.earned
        unit['possible'] += score.possible
    return [
        {**unit, 'passed': unit['earned'] >= unit['possible']}
        for unit in units.values() if unit['possible'] > 0
    ]


def learner_progress(course_key, learner):
    """
    The learner's course: sections → subsections → units with points, and the totals. A
    subsection's own total is the one of the gradebook (graded points, with a teacher's change).
    """
    course_grade = CourseGradeFactory().read(learner, course_key=course_key)
    structure = course_grade.course_data.structure
    sections = []
    for chapter in course_grade.chapter_grades.values():
        subsections = []
        for subsection_grade in chapter['sections']:
            units = _units(structure, subsection_grade)
            if not units:
                continue
            total = subsection_grade.graded_total if subsection_grade.graded else subsection_grade.all_total
            subsections.append({
                'id': str(subsection_grade.location),
                'name': subsection_grade.display_name,
                'graded': bool(subsection_grade.graded),
                'format': subsection_grade.format or '',
                **_total(total),
                'units': units,
            })
        if subsections:
            sections.append({'name': chapter['display_name'], 'subsections': subsections})
    units = [unit for section in sections for subsection in section['subsections'] for unit in subsection['units']]
    return {
        'percent': course_grade.percent,
        'passedUnits': sum(unit['passed'] for unit in units),
        'units': len(units),
        'sections': sections,
    }


class _GradebookReportView(DeveloperErrorViewMixin, APIView):
    """Same access as the gradebook API: the course team, with the writable gradebook on."""

    def learner(self, request, course_key):
        """The learner `user_id` of this course (enrolled now or before), else 400 / 404."""
        try:
            learner_id = int(request.GET.get('user_id', ''))
        except ValueError as error:
            raise self.api_error(
                status_code=status.HTTP_400_BAD_REQUEST,
                developer_message='user_id is required.',
                error_code='invalid_parameters',
            ) from error
        learner = get_user_model().objects.filter(id=learner_id).select_related('profile').first()
        if learner is None or not CourseEnrollment.objects.filter(user=learner, course_id=course_key).exists():
            raise self.api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                developer_message='The learner is not in this course.',
                error_code='unknown_learner',
            )
        return learner


@view_auth_classes()
class CourseLearnersView(_GradebookReportView):
    """
    **Use Case**
        The learners of a course to pick for the gradebook PDF report.

    **Example Request**
        GET /api/robbo/v1/gradebook/{course_id}/learners/

    **Response Values**
        course: {id, name} — the name for the report and its file name,
        learners: enrolled learners, most recently active in the course first, never active
            ones last: [{id, username, fullName, email, lastActivity (ISO 8601 or null)}]
    """

    @verify_course_exists("Requested learners for unknown course {course}")
    @verify_writable_gradebook_enabled
    @course_author_access_required
    def get(self, request, course_key):  # pylint: disable=unused-argument
        """Enrolled learners by last activity, with the course name."""
        return Response({
            'course': {'id': str(course_key), 'name': course_name(course_key)},
            'learners': course_learners(course_key),
        })


@view_auth_classes()
class LearnerProgressView(_GradebookReportView):
    """
    **Use Case**
        One learner's progress through the course by unit, for the gradebook PDF report.

    **Example Request**
        GET /api/robbo/v1/gradebook/{course_id}/progress/?user_id={user_id}

    **Response Values**
        learner: {id, username, fullName, email}
        percent: the course grade (0..1), as in the gradebook,
        passedUnits, units: units with all their points / units with points,
        sections: [{name, subsections: [{id, name, graded, format, earned, possible,
            units: [{name, earned, possible, passed}]}]}] — only what has points, in outline order.

    Only learners of this course (enrolled now or before): other user ids get the same 404 as
    unknown ones.
    """

    @verify_course_exists("Requested progress for unknown course {course}")
    @verify_writable_gradebook_enabled
    @course_author_access_required
    def get(self, request, course_key):
        """Progress of the learner `user_id`."""
        learner = self.learner(request, course_key)
        return Response({
            'learner': {
                'id': learner.id,
                'username': learner.username,
                'fullName': _full_name(learner),
                'email': learner.email,
            },
            **learner_progress(course_key, learner),
        })
