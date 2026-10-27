"""
Robbo: which learners a course-team member gets notifications about.

A member of the course team (staff, instructor, limited staff) chooses per course: all learners (the
default) or only selected ones. It narrows the notifications about one learner's work: learner
progress (robbo_progress.py) and «Новый ответ ждёт проверки» (ORA staff notifications, handlers.py).
Learners have no such choice — the API refuses it to them.

Stored as a UserPreference {"<course id>": [learner ids]}; a course missing there means all learners.

Copyright (C) 2026 Robbo <https://robbo.ru>
SPDX-License-Identifier: AGPL-3.0-only
Part of the Robbo Open edX distribution. See NOTICE at repository root.
"""
import json

from openedx.core.djangoapps.user_api.models import UserPreference

FOLLOW_KEY = 'robbo_notification_learners'


def _load(raw):
    try:
        value = json.loads(raw) if raw else {}
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def selection(user, course_id):
    """Selected learner ids for the course, or None for all learners."""
    chosen = _load(UserPreference.get_value(user, FOLLOW_KEY)).get(str(course_id))
    return None if chosen is None else [int(learner_id) for learner_id in chosen]


def set_selection(user, course_id, learner_ids):
    """learner_ids None = all learners again; a list (may be empty) = only those."""
    stored = _load(UserPreference.get_value(user, FOLLOW_KEY))
    if learner_ids is None:
        stored.pop(str(course_id), None)
    else:
        stored[str(course_id)] = sorted({int(learner_id) for learner_id in learner_ids})
    if stored:
        UserPreference.objects.update_or_create(user=user, key=FOLLOW_KEY, defaults={'value': json.dumps(stored)})
    else:
        UserPreference.objects.filter(user=user, key=FOLLOW_KEY).delete()


def following(course_id, learner_id, user_ids):
    """The recipients among user_ids who get notifications about this learner in this course."""
    user_ids = list(user_ids)
    narrowed = {
        user_id: _load(raw).get(str(course_id))
        for user_id, raw in UserPreference.objects.filter(user_id__in=user_ids, key=FOLLOW_KEY)
        .values_list('user_id', 'value')
    }
    return [
        user_id for user_id in user_ids
        if narrowed.get(user_id) is None or int(learner_id) in {int(i) for i in narrowed[user_id]}
    ]
