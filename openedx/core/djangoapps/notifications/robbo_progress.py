"""
Robbo: learner progress notifications for the course team (app ``learner_progress``).

* A test is a graded subsection with problems (ORA excluded). It is completed when the learner has
  a score on every problem in it.
* An open response assignment (ORA) counts once the learner submitted an answer.

Events: PROBLEM_WEIGHTED_SCORE_CHANGED (a problem got a score) and ORA_SUBMISSION_CREATED. A Celery
task looks at what the learner reached and picks, for every member of the course team (staff and
instructors, limited staff), the largest step that member has switched on:
course completed > all tests / all ORA > this test / this ORA. Each step is sent once per learner:
the sent notification lists the steps it covers in ``content_context['covers']``. An ORA with a
staff grading step already notifies the team («Новый ответ ждёт проверки»), so it gives no
«сдано задание» of its own, but still counts towards «все задания».

Copyright (C) 2026 Robbo <https://robbo.ru>
SPDX-License-Identifier: AGPL-3.0-only
Part of the Robbo Open edX distribution. See NOTICE at repository root.
"""
import logging

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from edx_django_utils.monitoring import set_code_owner_attribute
from opaque_keys.edx.keys import CourseKey, UsageKey

from openedx.core.djangoapps.notifications.utils import ROBBO_COURSE_TEAM_ROLES

log = logging.getLogger(__name__)
User = get_user_model()

APP = 'learner_progress'
TEST = 'learner_test_completed'
ALL_TESTS = 'learner_all_tests_completed'
ORA = 'learner_ora_submitted'
ALL_ORA = 'learner_all_ora_submitted'
COURSE = 'learner_course_completed'
# The score is saved in the same request that sends the signal; give the transaction time to commit.
DELAY_SECONDS = 5


def _number(value):
    value = round(value, 2)
    return int(value) if value == int(value) else value


def _course_structure(course_key):
    """Graded subsections with their problems, and every ORA of the course."""
    from xmodule.modulestore.django import modulestore  # pylint: disable=import-outside-toplevel
    store = modulestore()
    tests, oras = {}, {}
    with store.bulk_operations(course_key):
        course = store.get_course(course_key, depth=None)
        if course is None:
            return tests, oras

        def walk(block, test=None):
            if getattr(block, 'visible_to_staff_only', False):
                return
            if block.category == 'sequential' and block.graded:
                test = tests.setdefault(str(block.location), {'name': block.display_name, 'problems': {}})
            if block.category == 'openassessment':
                oras[str(block.location)] = {
                    'name': block.display_name,
                    'staff_step': any(
                        step.get('name') == 'staff-assessment' and step.get('required', True)
                        for step in (block.rubric_assessments or [])
                    ),
                }
                return
            if test is not None and getattr(block, 'has_score', False) and not block.has_children:
                test['problems'][str(block.location)] = getattr(block, 'weight', None)
            for child in block.get_children():
                walk(child, test)

        walk(course)
    return {key: value for key, value in tests.items() if value['problems']}, oras


def _scores(user_id, course_key, problems):
    """{problem: (grade, max_grade)} for problems the learner has a score on."""
    from lms.djangoapps.courseware.models import StudentModule  # pylint: disable=import-outside-toplevel
    keys = [UsageKey.from_string(problem) for problem in problems]
    rows = StudentModule.objects.filter(
        student_id=user_id, course_id=course_key, module_state_key__in=keys, grade__isnull=False,
    ).values_list('module_state_key', 'grade', 'max_grade')
    return {str(key): (grade, max_grade) for key, grade, max_grade in rows}


def _test_points(test, scores):
    earned = possible = 0
    for problem, weight in test['problems'].items():
        grade, max_grade = scores.get(problem, (0, 0))
        if weight is not None and max_grade:
            earned += grade / max_grade * weight
            possible += weight
        else:
            earned += grade or 0
            possible += max_grade or 0
    return _number(earned), _number(possible)


def _submitted_oras(user, course_key, oras):
    from common.djangoapps.student.models import anonymous_id_for_user  # pylint: disable=import-outside-toplevel
    from submissions.models import Submission  # pylint: disable=import-outside-toplevel
    if not oras:
        return set()
    anonymous_id = anonymous_id_for_user(user, course_key)
    return set(Submission.objects.filter(
        student_item__student_id=anonymous_id, student_item__course_id=str(course_key),
        student_item__item_id__in=list(oras), status='A',
    ).values_list('student_item__item_id', flat=True))


def _course_team(course_key, learner_id):
    from common.djangoapps.student.models import CourseAccessRole  # pylint: disable=import-outside-toplevel
    team = set(CourseAccessRole.objects.filter(
        course_id=course_key, role__in=ROBBO_COURSE_TEAM_ROLES, user__is_active=True,
    ).values_list('user_id', flat=True))
    team.discard(learner_id)
    return sorted(team)


def _already_covered(course_key, learner_id, mark):
    from openedx.core.djangoapps.notifications.models import Notification  # pylint: disable=import-outside-toplevel
    return Notification.objects.filter(
        course_id=course_key, app_name=APP,
        content_context__contains={'learner_id': learner_id, 'covers': [mark]},
    ).exists()


def _enabled_types(team, course_key):
    """{user_id: set of learner_progress types switched on}; no preference yet = defaults (all on)."""
    from openedx.core.djangoapps.notifications.models import (  # pylint: disable=import-outside-toplevel
        CourseNotificationPreference,
    )
    from openedx.core.djangoapps.notifications.tasks import update_user_preference  # pylint: disable=import-outside-toplevel
    every = {TEST, ALL_TESTS, ORA, ALL_ORA, COURSE}
    enabled = {user_id: set(every) for user_id in team}
    for preference in CourseNotificationPreference.objects.filter(user_id__in=team, course_id=course_key):
        preference = update_user_preference(preference, preference.user_id, course_key)
        if not preference.get_app_config(APP).get('enabled', False):
            enabled[preference.user_id] = set()
            continue
        enabled[preference.user_id] = {
            kind for kind in every if preference.is_enabled_for_any_channel(APP, kind)
        }
    return enabled


def _send(course_key, learner, steps, team):
    """steps: [(type, context, url, mark)] from the largest to the smallest."""
    from openedx.core.djangoapps.notifications.tasks import send_notifications  # pylint: disable=import-outside-toplevel
    marks = [mark for _, _, _, mark in steps]
    # Members who chose only some learners of this course hear about those only (robbo_followers.py).
    from openedx.core.djangoapps.notifications.robbo_followers import following  # pylint: disable=import-outside-toplevel
    team = following(course_key, learner.id, team)
    enabled = _enabled_types(team, course_key)
    by_type = {}
    for user_id in team:
        for kind, context, url, _ in steps:
            if kind in enabled.get(user_id, ()):
                by_type.setdefault(kind, (context, url, []))[2].append(user_id)
                break
    for kind, (context, url, user_ids) in by_type.items():
        context = {**context, 'learner_id': learner.id, 'covers': marks}
        send_notifications.delay(user_ids, str(course_key), APP, kind, context, url)
    log.info('Robbo progress: learner %s in %s, steps %s, sent %s', learner.id, course_key, marks,
             {kind: len(value[2]) for kind, value in by_type.items()})


@shared_task(ignore_result=True)
@set_code_owner_attribute
def check_learner_progress(user_id, course_id, usage_id):
    """What the learner reached after a score or an ORA submission on ``usage_id``."""
    from openedx.core.djangoapps.content.course_overviews.models import CourseOverview  # pylint: disable=import-outside-toplevel
    course_key = CourseKey.from_string(course_id)
    learner = User.objects.filter(id=user_id).select_related('profile').first()
    team = _course_team(course_key, user_id)
    if learner is None or not team:
        return
    tests, oras = _course_structure(course_key)
    usage_id = str(usage_id)
    test_id = next((key for key, test in tests.items() if usage_id in test['problems']), None)
    if usage_id not in oras and test_id is None:
        return

    scores = _scores(user_id, course_key, [p for test in tests.values() for p in test['problems']])
    done_tests = {key for key, test in tests.items() if all(p in scores for p in test['problems'])}
    done_oras = _submitted_oras(learner, course_key, oras)
    if usage_id in oras and usage_id not in done_oras:
        return
    if test_id is not None and test_id not in done_tests:
        return

    name = getattr(getattr(learner, 'profile', None), 'name', '') or learner.username
    overview = CourseOverview.objects.filter(id=course_key).first()
    base = {'learner_name': name, 'course_name': overview.display_name if overview else str(course_key)}
    lms = settings.LMS_ROOT_URL
    progress_url = f'{lms}/courses/{course_key}/progress/{user_id}/'
    all_tests = bool(tests) and len(done_tests) == len(tests)
    all_oras = bool(oras) and len(done_oras) == len(oras)
    course_done = (bool(tests) or bool(oras)) and (all_tests or not tests) and (all_oras or not oras)

    steps = []
    if course_done:
        steps.append((COURSE, base, progress_url, f'{COURSE}:course'))
    if test_id is not None:
        if all_tests:
            steps.append((ALL_TESTS, {**base, 'count': len(tests)}, progress_url, f'{ALL_TESTS}:course'))
        earned, possible = _test_points(tests[test_id], scores)
        steps.append((TEST, {
            **base, 'test_name': tests[test_id]['name'], 'points_earned': earned, 'points_possible': possible,
        }, progress_url, f'{TEST}:{test_id}'))
    else:
        if all_oras:
            steps.append((ALL_ORA, {**base, 'count': len(oras)}, progress_url, f'{ALL_ORA}:course'))
        if not oras[usage_id]['staff_step']:
            ora_url = f'{lms}/courses/{course_key}/jump_to/{usage_id}'
            steps.append((ORA, {**base, 'ora_name': oras[usage_id]['name']}, ora_url, f'{ORA}:{usage_id}'))

    # A low score on the test just completed: the team hears about it once (robbo_events.py helpers).
    if test_id is not None:
        earned, possible = _test_points(tests[test_id], scores)
        threshold = getattr(settings, 'ROBBO_NOTIFICATIONS_LOW_SCORE_PERCENT', 50)
        if possible and earned * 100 < possible * threshold:
            from openedx.core.djangoapps.notifications.robbo_events import notify_team_about  # pylint: disable=import-outside-toplevel
            notify_team_about(user_id, course_key, 'learner_low_score', {
                'learner_name': name, 'test_name': tests[test_id]['name'],
                'points_earned': earned, 'points_possible': possible,
            }, progress_url, mark=f'low:{user_id}:{test_id}')

    # Steps reached earlier are not repeated (re-answering a test, a second ORA attempt).
    steps = [step for step in steps if not _already_covered(course_key, user_id, step[3])]
    if not steps:
        return
    # Two scores of one test a second apart must not both send it.
    if not cache.add(f'robbo-progress:{course_key}:{user_id}:{steps[-1][3]}', 1, 600):
        return
    _send(course_key, learner, steps, team)


def on_problem_score(sender, **kwargs):  # pylint: disable=unused-argument
    if kwargs.get('score_deleted') or not kwargs.get('user_id'):
        return
    check_learner_progress.apply_async(
        (kwargs['user_id'], str(kwargs['course_id']), str(kwargs['usage_id'])), countdown=DELAY_SECONDS,
    )


def on_ora_submission(signal, sender, submission, **kwargs):  # pylint: disable=unused-argument
    from common.djangoapps.student.models import user_by_anonymous_id  # pylint: disable=import-outside-toplevel
    user = user_by_anonymous_id(submission.anonymous_user_id)
    if user is None or not submission.location:
        return
    location = UsageKey.from_string(str(submission.location))
    check_learner_progress.apply_async(
        (user.id, str(location.course_key), str(location)), countdown=DELAY_SECONDS,
    )


def connect():
    """LMS only: the grades signal lives there."""
    from lms.djangoapps.grades.signals.signals import PROBLEM_WEIGHTED_SCORE_CHANGED  # pylint: disable=import-outside-toplevel
    from openedx_events.learning.signals import ORA_SUBMISSION_CREATED  # pylint: disable=import-outside-toplevel
    PROBLEM_WEIGHTED_SCORE_CHANGED.connect(on_problem_score, dispatch_uid='robbo_progress_problem_score')
    ORA_SUBMISSION_CREATED.connect(on_ora_submission, dispatch_uid='robbo_progress_ora_submission')
