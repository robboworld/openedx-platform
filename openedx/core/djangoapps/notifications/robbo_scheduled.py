"""
Robbo: notifications that depend on time, sent by `./manage.py lms robbo_notifications` (cron).

* learner_deadline_soon     — learner: a graded subsection or an ORA is due within the window, not done yet;
* learner_section_released  — learner: a section / subsection opened in the last day (not at course start);
* learner_missed_deadline   — team: the due date passed in the last day, the learner did not finish;
* submission_review_overdue — team: an answer to an ORA graded by the team waits longer than N days;
* learner_inactive          — team: no activity in the course for N days (once per quiet period);
* course_weekly_report      — team: a week in numbers (Mondays, or --weekly).

Every notification carries a mark, so running the command again does not repeat it. Personal due
dates (edx-when overrides) are not taken into account: the dates come from the course.

Copyright (C) 2026 Robbo <https://robbo.ru>
SPDX-License-Identifier: AGPL-3.0-only
Part of the Robbo Open edX distribution. See NOTICE at repository root.
"""
import logging
from datetime import datetime, timedelta, timezone as dt_timezone

from dateutil.parser import isoparse
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Max, Q
from django.utils import timezone
from opaque_keys.edx.keys import UsageKey

from openedx.core.djangoapps.notifications.robbo_events import (
    course_team, learner_name, lms_url, notify, notify_team_about,
)

log = logging.getLogger(__name__)
User = get_user_model()

DEFAULTS = {
    'deadline_window_hours': 48,
    'released_window_hours': 24,
    'missed_window_hours': 24,
    'review_overdue_days': 3,
    'inactive_days': 14,
}


def _setting(name):
    return getattr(settings, f'ROBBO_NOTIFICATIONS_{name.upper()}', DEFAULTS[name])


def _aware(value):
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = isoparse(value)
        except ValueError:
            return None
    if isinstance(value, datetime) and timezone.is_naive(value):
        value = value.replace(tzinfo=dt_timezone.utc)
    return value


def active_courses(now):
    from openedx.core.djangoapps.content.course_overviews.models import CourseOverview  # pylint: disable=import-outside-toplevel
    from openedx.core.djangoapps.notifications.config.waffle import ENABLE_NOTIFICATIONS  # pylint: disable=import-outside-toplevel
    courses = CourseOverview.objects.filter(Q(start__lte=now) | Q(start__isnull=True)).filter(
        Q(end__isnull=True) | Q(end__gte=now - timedelta(days=1)))
    return [course for course in courses if ENABLE_NOTIFICATIONS.is_enabled(course.id)]


def course_learners(course_key):
    team = set(course_team(course_key))
    return [
        user for user in User.objects.filter(
            courseenrollment__course_id=course_key, courseenrollment__is_active=True, is_active=True,
        ).select_related('profile').distinct()
        if user.id not in team
    ]


class CourseState:
    """What a course is made of and what its learners have done (one modulestore walk per course)."""

    def __init__(self, overview):
        from openedx.core.djangoapps.notifications.robbo_progress import _course_structure  # pylint: disable=import-outside-toplevel
        from xmodule.modulestore.django import modulestore  # pylint: disable=import-outside-toplevel
        self.overview = overview
        self.key = overview.id
        self.tests, self.oras = _course_structure(self.key)
        self.due = {}       # block id -> (name, due, kind)
        self.released = {}  # block id -> (name, start)
        store = modulestore()
        with store.bulk_operations(self.key):
            course = store.get_course(self.key, depth=None)
            if course is not None:
                self._walk(course)
        self.learners = course_learners(self.key)
        self._scores = None
        self._submitted = None

    def _walk(self, block, parent_start=None):
        if getattr(block, 'visible_to_staff_only', False):
            return
        block_id = str(block.location)
        start = _aware(block.start) if block.start else None
        # A subsection opening together with its section is announced once, by the section: only a
        # subsection with a start of its own (not inherited, more than a minute apart) counts.
        own_start = block.category == 'sequential' and block.fields['start'].is_set_on(block) and (
            parent_start is None or start is None or abs((start - parent_start).total_seconds()) > 60)
        if start and (block.category == 'chapter' or own_start):
            self.released[block_id] = (block.display_name, start)
        if block.category == 'sequential' and block_id in self.tests and block.due:
            self.due[block_id] = (block.display_name, _aware(block.due), 'test')
        if block.category == 'openassessment' and getattr(block, 'submission_due', None):
            self.due[block_id] = (block.display_name, _aware(block.submission_due), 'ora')
        if block.category not in ('openassessment',):
            for child in block.get_children():
                self._walk(child, start if block.category == 'chapter' else parent_start)

    def scores(self):
        """{learner id: set of scored problems}."""
        if self._scores is None:
            from lms.djangoapps.courseware.models import StudentModule  # pylint: disable=import-outside-toplevel
            problems = [UsageKey.from_string(p) for test in self.tests.values() for p in test['problems']]
            self._scores = {}
            for student_id, key in StudentModule.objects.filter(
                course_id=self.key, module_state_key__in=problems, grade__isnull=False,
            ).values_list('student_id', 'module_state_key'):
                self._scores.setdefault(student_id, set()).add(str(key))
        return self._scores

    def submitted(self):
        """{anonymous id: set of ORA ids with an answer}."""
        if self._submitted is None:
            from submissions.models import Submission  # pylint: disable=import-outside-toplevel
            self._submitted = {}
            for student, item in Submission.objects.filter(
                student_item__course_id=str(self.key), student_item__item_id__in=list(self.oras), status='A',
            ).values_list('student_item__student_id', 'student_item__item_id'):
                self._submitted.setdefault(student, set()).add(item)
        return self._submitted

    def done(self, learner, block_id, kind):
        if kind == 'test':
            return set(self.tests[block_id]['problems']) <= self.scores().get(learner.id, set())
        from common.djangoapps.student.models import anonymous_id_for_user  # pylint: disable=import-outside-toplevel
        return block_id in self.submitted().get(anonymous_id_for_user(learner, self.key), set())


def deadlines_soon(state, now):
    sent = 0
    until = now + timedelta(hours=_setting('deadline_window_hours'))
    for block_id, (name, due, kind) in state.due.items():
        if not due or not now < due <= until:
            continue
        for learner in state.learners:
            if state.done(learner, block_id, kind):
                continue
            sent += notify([learner.id], state.key, 'learning', 'learner_deadline_soon',
                           {'block_name': name, 'due': due.isoformat(), 'due_text': due.strftime('%Y-%m-%d %H:%M UTC')},
                           lms_url(f'/courses/{state.key}/jump_to/{block_id}'), mark=f'deadline:{block_id}:{due.date()}')
    return sent


def sections_released(state, now):
    sent = 0
    since = now - timedelta(hours=_setting('released_window_hours'))
    course_start = _aware(state.overview.start)
    for block_id, (name, start) in state.released.items():
        if not start or not since < start <= now or (course_start and start <= course_start):
            continue
        sent += notify([learner.id for learner in state.learners], state.key, 'learning',
                       'learner_section_released', {'section_name': name},
                       lms_url(f'/courses/{state.key}/jump_to/{block_id}'), mark=f'released:{block_id}:{start.date()}')
    return sent


def missed_deadlines(state, now):
    sent = 0
    since = now - timedelta(hours=_setting('missed_window_hours'))
    for block_id, (name, due, kind) in state.due.items():
        if not due or not since < due <= now:
            continue
        for learner in state.learners:
            if state.done(learner, block_id, kind):
                continue
            sent += notify_team_about(learner.id, state.key, 'learner_missed_deadline',
                                      {'learner_name': learner_name(learner), 'block_name': name},
                                      lms_url(f'/courses/{state.key}/progress/{learner.id}/'),
                                      mark=f'missed:{learner.id}:{block_id}')
    return sent


def reviews_overdue(state, now):
    from common.djangoapps.student.models import user_by_anonymous_id  # pylint: disable=import-outside-toplevel
    from openassessment.workflow.models import AssessmentWorkflow  # pylint: disable=import-outside-toplevel
    from submissions.models import Submission  # pylint: disable=import-outside-toplevel
    sent = 0
    days = _setting('review_overdue_days')
    staff_oras = {ora_id: ora for ora_id, ora in state.oras.items() if ora['staff_step']}
    if not staff_oras:
        return 0
    team = set(course_team(state.key))
    waiting = Submission.objects.filter(
        student_item__course_id=str(state.key), student_item__item_id__in=list(staff_oras), status='A',
        created_at__lte=now - timedelta(days=days),
    ).values_list('uuid', 'student_item__student_id', 'student_item__item_id', 'created_at')
    for uuid, anonymous_id, item_id, created in waiting:
        workflow = AssessmentWorkflow.objects.filter(submission_uuid=uuid).first()
        if workflow is None or workflow.status in ('done', 'cancelled'):
            continue
        learner = user_by_anonymous_id(anonymous_id)
        if learner is None or learner.id in team:
            continue  # answers of the course team are not learners' work
        waited = (now - created).days
        ora_url = f"{getattr(settings, 'ORA_GRADING_MICROFRONTEND_URL', '')}/{item_id}"
        sent += notify_team_about(learner.id, state.key, 'submission_review_overdue', {
            'learner_name': learner_name(learner), 'ora_name': staff_oras[item_id]['name'], 'days': waited,
        }, ora_url, mark=f'overdue:{uuid}')
    return sent


def last_activity(state):
    """{learner id: last moment the learner did something in the course}."""
    from common.djangoapps.student.models import CourseEnrollment  # pylint: disable=import-outside-toplevel
    from lms.djangoapps.courseware.models import StudentModule  # pylint: disable=import-outside-toplevel
    ids = [learner.id for learner in state.learners]
    seen = dict(StudentModule.objects.filter(course_id=state.key, student_id__in=ids)
                .values('student_id').annotate(last=Max('modified')).values_list('student_id', 'last'))
    for user_id, created in CourseEnrollment.objects.filter(course_id=state.key, user_id__in=ids).values_list(
            'user_id', 'created'):
        seen.setdefault(user_id, created)
    return seen


def inactive_learners(state, now):
    sent = 0
    days = _setting('inactive_days')
    seen = last_activity(state)
    for learner in state.learners:
        last = seen.get(learner.id)
        if not last or now - last < timedelta(days=days):
            continue
        sent += notify_team_about(learner.id, state.key, 'learner_inactive', {
            'learner_name': learner_name(learner), 'days': (now - last).days,
        }, lms_url(f'/courses/{state.key}/progress/{learner.id}/'), mark=f'inactive:{learner.id}:{last.date()}')
    return sent


def weekly_report(state, now):
    from lms.djangoapps.courseware.models import StudentModule  # pylint: disable=import-outside-toplevel
    from openassessment.workflow.models import AssessmentWorkflow  # pylint: disable=import-outside-toplevel
    from submissions.models import Submission  # pylint: disable=import-outside-toplevel
    week_ago = now - timedelta(days=7)
    team = course_team(state.key)
    if not team:
        return 0
    ids = {learner.id for learner in state.learners}
    # Tests completed this week: every problem scored, the last score within the week.
    finished = {}
    problems = {p: t for t, test in state.tests.items() for p in test['problems']}
    for student_id, key, modified in StudentModule.objects.filter(
        course_id=state.key, student_id__in=ids, grade__isnull=False,
        module_state_key__in=[UsageKey.from_string(p) for p in problems],
    ).values_list('student_id', 'module_state_key', 'modified'):
        test = problems[str(key)]
        entry = finished.setdefault((student_id, test), [set(), None])
        entry[0].add(str(key))
        entry[1] = max(entry[1], modified) if entry[1] else modified
    tests_done = sum(
        1 for (_, test), (scored, last) in finished.items()
        if set(state.tests[test]['problems']) <= scored and last >= week_ago
    )
    from common.djangoapps.student.models import anonymous_id_for_user  # pylint: disable=import-outside-toplevel
    learner_ids = [anonymous_id_for_user(learner, state.key) for learner in state.learners]
    answers = Submission.objects.filter(student_item__course_id=str(state.key), student_item__student_id__in=learner_ids,
                                        student_item__item_id__in=list(state.oras), status='A')
    ora_submitted = answers.filter(created_at__gte=week_ago).count()
    staff_items = [ora_id for ora_id, ora in state.oras.items() if ora['staff_step']]
    uuids = list(answers.filter(student_item__item_id__in=staff_items).values_list('uuid', flat=True))
    waiting_review = AssessmentWorkflow.objects.filter(submission_uuid__in=uuids).exclude(
        status__in=('done', 'cancelled')).count()
    seen = last_activity(state)
    inactive = sum(1 for learner in state.learners
                   if seen.get(learner.id) and now - seen[learner.id] >= timedelta(days=_setting('inactive_days')))
    week = now.isocalendar()
    return notify(team, state.key, 'learner_progress', 'course_weekly_report', {
        'tests_done': tests_done, 'ora_submitted': ora_submitted, 'waiting_review': waiting_review,
        'inactive': inactive, 'learners': len(state.learners),
    }, lms_url(f'/courses/{state.key}/instructor'), mark=f'weekly:{state.key}:{week[0]}-{week[1]}')


CHECKS = {
    'deadline': deadlines_soon,
    'released': sections_released,
    'missed': missed_deadlines,
    'overdue': reviews_overdue,
    'inactive': inactive_learners,
    'weekly': weekly_report,
}


def run(only=None, weekly=None, course_ids=None, now=None):
    """Runs the checks over active courses. Returns {check: notifications queued}."""
    now = now or timezone.now()
    names = list(only or CHECKS)
    if weekly is None:
        weekly = now.weekday() == 0
    if not weekly and 'weekly' in names and not only:
        names.remove('weekly')
    totals = dict.fromkeys(names, 0)
    for overview in active_courses(now):
        if course_ids and str(overview.id) not in course_ids:
            continue
        try:
            state = CourseState(overview)
            for name in names:
                totals[name] += CHECKS[name](state, now)
        except Exception:  # pylint: disable=broad-except
            log.exception('Robbo scheduled notifications failed for %s', overview.id)
    log.info('Robbo scheduled notifications: %s', totals)
    return totals
