"""
Robbo: notifications raised by platform events (scheduled ones: robbo_scheduled.py).

Learners (app «learning»): certificate ready, grade changed by the course team, enrolled by someone
else. Course team (app «learner_progress»): a learner enrolled or left. Studio (app «authoring»):
a co-author published changes, a course import / export finished, you were added to a course team.

Whoever caused an event in the current request is never notified about it. Team notifications about
one learner honour each member's choice of learners (robbo_followers.py).

Copyright (C) 2026 Robbo <https://robbo.ru>
SPDX-License-Identifier: AGPL-3.0-only
Part of the Robbo Open edX distribution. See NOTICE at repository root.
"""
import logging

from celery import shared_task
from crum import get_current_user
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models.signals import post_save
from edx_django_utils.monitoring import set_code_owner_attribute
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey, UsageKey

log = logging.getLogger(__name__)
User = get_user_model()

# One «co-author published» per author and course in this many seconds (Studio publishes often).
PUBLISH_THROTTLE = 3600
# Seconds a marked notification is locked in the cache before its row exists.
MARK_LOCK = 600


def _actor():
    user = get_current_user()
    return user if user is not None and getattr(user, 'is_authenticated', False) else None


def lms_url(path):
    return f"{getattr(settings, 'LMS_ROOT_URL', '').rstrip('/')}{path}"


def studio_url(course_key):
    base = getattr(settings, 'CMS_ROOT_URL', '') or f"//{getattr(settings, 'CMS_BASE', '')}"
    return f'{base.rstrip("/")}/course/{course_key}'


def course_name(course_key):
    from openedx.core.djangoapps.content.course_overviews.models import CourseOverview  # pylint: disable=import-outside-toplevel
    overview = CourseOverview.objects.filter(id=course_key).first()
    return overview.display_name if overview else str(course_key)


def learner_name(user):
    return getattr(getattr(user, 'profile', None), 'name', '') or user.username


def course_team(course_key, exclude=()):
    from common.djangoapps.student.models import CourseAccessRole  # pylint: disable=import-outside-toplevel
    from openedx.core.djangoapps.notifications.utils import ROBBO_COURSE_TEAM_ROLES  # pylint: disable=import-outside-toplevel
    ids = set(CourseAccessRole.objects.filter(
        course_id=course_key, role__in=ROBBO_COURSE_TEAM_ROLES, user__is_active=True,
    ).values_list('user_id', flat=True))
    return sorted(ids - set(exclude))


def already_sent(user_id, notification_type, mark):
    from openedx.core.djangoapps.notifications.models import Notification  # pylint: disable=import-outside-toplevel
    return Notification.objects.filter(
        user_id=user_id, notification_type=notification_type, content_context__contains={'mark': mark},
    ).exists()


def notify(user_ids, course_key, app, notification_type, context, url, mark=None):
    """Queues one notification type for these users (send_notifications checks preferences)."""
    from openedx.core.djangoapps.notifications.tasks import send_notifications  # pylint: disable=import-outside-toplevel
    user_ids = sorted(set(user_ids))
    if mark:
        # The notification is created by a Celery task a moment later: the cache key stops a second
        # event in that moment (a certificate saved twice in a row), the stored mark — everything after.
        user_ids = [
            user_id for user_id in user_ids
            if not already_sent(user_id, notification_type, mark)
            and cache.add(f'robbo-mark:{user_id}:{notification_type}:{mark}', 1, MARK_LOCK)
        ]
    if not user_ids:
        return 0
    context = {'course_name': course_name(course_key), **context}
    if mark:
        context['mark'] = mark
    send_notifications.delay(user_ids, str(course_key), app, notification_type, context, url)
    return len(user_ids)


def notify_team_about(learner_id, course_key, notification_type, context, url, mark=None, exclude=()):
    """A learner_progress notification to the team members who follow this learner."""
    from openedx.core.djangoapps.notifications.robbo_followers import following  # pylint: disable=import-outside-toplevel
    team = following(course_key, learner_id, course_team(course_key, exclude=(learner_id, *exclude)))
    return notify(team, course_key, 'learner_progress', notification_type,
                  {'learner_id': learner_id, **context}, url, mark=mark)


# --- learners -------------------------------------------------------------------------------------

def on_certificate_created(signal, sender, certificate, **kwargs):  # pylint: disable=unused-argument
    if getattr(certificate, 'current_status', 'downloadable') != 'downloadable':
        return
    course_key = certificate.course.course_key
    notify([certificate.user.id], course_key, 'learning', 'learner_certificate_issued', {},
           lms_url(f'/courses/{course_key}/progress'), mark=f'certificate:{course_key}')


def on_enrollment_created(signal, sender, enrollment, **kwargs):  # pylint: disable=unused-argument
    course_key = enrollment.course.course_key
    learner = User.objects.filter(id=enrollment.user.id).select_related('profile').first()
    if learner is None or learner.id in course_team(course_key):
        return
    actor = _actor()
    notify_team_about(learner.id, course_key, 'learner_enrolled', {'learner_name': learner_name(learner)},
                      lms_url(f'/courses/{course_key}/progress/{learner.id}/'),
                      exclude=(actor.id,) if actor else ())
    if actor is not None and actor.id != learner.id:
        notify([learner.id], course_key, 'learning', 'learner_added_to_course', {},
               lms_url(f'/courses/{course_key}/course/'))


def on_unenrollment(signal, sender, enrollment, **kwargs):  # pylint: disable=unused-argument
    course_key = enrollment.course.course_key
    learner = User.objects.filter(id=enrollment.user.id).select_related('profile').first()
    if learner is None or learner.id in course_team(course_key):
        return
    actor = _actor()
    notify_team_about(learner.id, course_key, 'learner_unenrolled', {'learner_name': learner_name(learner)},
                      lms_url(f'/courses/{course_key}/instructor'), exclude=(actor.id,) if actor else ())


@shared_task(ignore_result=True)
@set_code_owner_attribute
def notify_grade_changed(user_id, course_id, usage_id, earned, possible):
    """The course team changed a learner's score on a problem or a subsection."""
    from xmodule.modulestore.django import modulestore  # pylint: disable=import-outside-toplevel
    from openedx.core.djangoapps.notifications.robbo_progress import _number  # pylint: disable=import-outside-toplevel
    course_key = CourseKey.from_string(course_id)
    usage_key = UsageKey.from_string(usage_id)
    try:
        name = modulestore().get_item(usage_key).display_name
    except Exception:  # pylint: disable=broad-except
        name = usage_key.block_id
    notify([user_id], course_key, 'learning', 'learner_grade_changed',
           {'item_name': name, 'points_earned': _number(earned or 0), 'points_possible': _number(possible or 0)},
           lms_url(f'/courses/{course_key}/jump_to/{usage_key}'))


def on_problem_score(sender, **kwargs):  # pylint: disable=unused-argument
    """A score set by someone else than the learner in a request: a course-team change."""
    actor = _actor()
    user_id = kwargs.get('user_id')
    usage_id = str(kwargs.get('usage_id', ''))
    if actor is None or not user_id or actor.id == int(user_id) or kwargs.get('score_deleted'):
        return
    if 'type@openassessment' in usage_id:
        return  # ORA grading has its own «Задание проверено»
    notify_grade_changed.delay(int(user_id), str(kwargs['course_id']), usage_id,
                               kwargs.get('weighted_earned'), kwargs.get('weighted_possible'))


def on_subsection_override_saved(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """A subsection grade override saved by someone else than the learner (gradebook, grades API)."""
    actor = _actor()
    grade = instance.grade
    if actor is None or actor.id == grade.user_id:
        return
    earned = instance.earned_graded_override if instance.earned_graded_override is not None else grade.earned_graded
    possible = (instance.possible_graded_override if instance.possible_graded_override is not None
                else grade.possible_graded)
    notify_grade_changed.delay(grade.user_id, str(grade.course_id), str(grade.usage_key), earned, possible)


# --- Studio ---------------------------------------------------------------------------------------

def on_course_published(sender, course_key, **kwargs):  # pylint: disable=unused-argument
    actor = _actor()
    if actor is None or not isinstance(course_key, CourseKey) or getattr(course_key, 'deprecated', False):
        return
    if not cache.add(f'robbo-published:{course_key}:{actor.id}', 1, PUBLISH_THROTTLE):
        return
    team = course_team(course_key, exclude=(actor.id,))
    notify(team, course_key, 'authoring', 'course_published_by_coauthor', {'author_name': learner_name(actor)},
           studio_url(course_key))


def on_user_task_stopped(sender, status, **kwargs):  # pylint: disable=unused-argument
    """Course import / export in Studio finished (or failed): tell the user who started it."""
    from user_tasks.models import UserTaskStatus  # pylint: disable=import-outside-toplevel
    name = status.name or ''
    operation = 'import' if name.startswith('Import of ') else 'export' if name.startswith('Export of ') else ''
    if not operation:
        return
    try:
        course_key = CourseKey.from_string(name.split(' ')[2])
    except (InvalidKeyError, IndexError):
        return  # libraries and other keys
    result = 'succeeded' if status.state == UserTaskStatus.SUCCEEDED else 'failed'
    notify([status.user_id], course_key, 'authoring', 'course_import_export',
           {'operation': operation, 'result': result}, studio_url(course_key).replace('/course/', f'/{operation}/'))


def on_course_role_saved(sender, instance, created, **kwargs):  # pylint: disable=unused-argument
    """Added to a course team (once, even when staff and instructor come together)."""
    from common.djangoapps.student.models import CourseAccessRole  # pylint: disable=import-outside-toplevel
    from openedx.core.djangoapps.notifications.utils import ROBBO_COURSE_TEAM_ROLES  # pylint: disable=import-outside-toplevel
    if not created or instance.role not in ROBBO_COURSE_TEAM_ROLES or not instance.course_id:
        return
    actor = _actor()
    if actor is not None and actor.id == instance.user_id:
        return
    roles = CourseAccessRole.objects.filter(
        user_id=instance.user_id, course_id=instance.course_id, role__in=ROBBO_COURSE_TEAM_ROLES,
    ).count()
    if roles != 1:
        return
    notify([instance.user_id], instance.course_id, 'authoring', 'added_to_course_team', {},
           studio_url(instance.course_id))


def connect():
    """Every receiver whose signal exists in this process (LMS, Studio, their workers)."""
    from openedx_events.learning.signals import (  # pylint: disable=import-outside-toplevel
        CERTIFICATE_CREATED, COURSE_ENROLLMENT_CREATED, COURSE_UNENROLLMENT_COMPLETED,
    )
    from common.djangoapps.student.models import CourseAccessRole  # pylint: disable=import-outside-toplevel
    CERTIFICATE_CREATED.connect(on_certificate_created, dispatch_uid='robbo_events_certificate')
    COURSE_ENROLLMENT_CREATED.connect(on_enrollment_created, dispatch_uid='robbo_events_enrollment')
    COURSE_UNENROLLMENT_COMPLETED.connect(on_unenrollment, dispatch_uid='robbo_events_unenrollment')
    post_save.connect(on_course_role_saved, sender=CourseAccessRole, dispatch_uid='robbo_events_course_role')
    try:
        from lms.djangoapps.grades.models import PersistentSubsectionGradeOverride  # pylint: disable=import-outside-toplevel
        from lms.djangoapps.grades.signals.signals import (  # pylint: disable=import-outside-toplevel
            PROBLEM_WEIGHTED_SCORE_CHANGED,
        )
        PROBLEM_WEIGHTED_SCORE_CHANGED.connect(on_problem_score, dispatch_uid='robbo_events_problem_score')
        # The gradebook saves overrides without SUBSECTION_OVERRIDE_CHANGED: listen to the model.
        post_save.connect(on_subsection_override_saved, sender=PersistentSubsectionGradeOverride,
                          dispatch_uid='robbo_events_override')
    except ImportError:
        pass
    try:
        from xmodule.modulestore.django import SignalHandler  # pylint: disable=import-outside-toplevel
        SignalHandler.course_published.connect(on_course_published, dispatch_uid='robbo_events_published')
    except ImportError:
        pass
    try:
        from user_tasks import user_task_stopped  # pylint: disable=import-outside-toplevel
        user_task_stopped.connect(on_user_task_stopped, dispatch_uid='robbo_events_user_task')
    except ImportError:
        pass
