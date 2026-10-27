"""
Robbo: stored notification settings «Для всех курсов».

Open edX keeps preferences per course only and shows an aggregate as the account-wide view (a channel
is on when it is on in any course, cadences become «Mixed»). Changing one course then changed that
view and marked every other course as having its own settings. Here the account-wide settings are
stored per user (a UserPreference with {"app.type": {web, email, email_cadence}}):

* a course «has its own settings» when a type it shows differs from them;
* changing them changes only the courses that still follow them on that type and channel; courses
  with their own value keep it;
* resetting a course gives it exactly these settings; a new course preference starts with them.

The first read builds them from the user's courses (the most common value of every channel).
Push and channels the LMS marks non-editable are left alone.

Copyright (C) 2026 Robbo <https://robbo.ru>
SPDX-License-Identifier: AGPL-3.0-only
Part of the Robbo Open edX distribution. See NOTICE at repository root.
"""
import copy
import json
from collections import Counter

from django.db.models.signals import post_save
from django.dispatch import receiver

from openedx.core.djangoapps.notifications.base_notification import NotificationAppManager
from openedx.core.djangoapps.notifications.models import CourseNotificationPreference
from openedx.core.djangoapps.user_api.models import UserPreference

ACCOUNT_KEY = 'robbo_notification_account_config'
CHANNELS = ('web', 'email', 'email_cadence')


def _key(app, type_id):
    return f'{app}.{type_id}'


def _types(config):
    """(app, type_id, type_config, locked channels) for every type of a full config."""
    for app, app_config in (config or {}).items():
        locked = app_config.get('non_editable', {}) or {}
        for type_id, type_config in app_config.get('notification_types', {}).items():
            yield app, type_id, type_config, locked.get(type_id, [])


def _template():
    return NotificationAppManager().get_notification_app_preferences()


def _course_preferences(user):
    return [
        CourseNotificationPreference.get_user_course_preference(user.id, preference.course_id)
        for preference in CourseNotificationPreference.objects.filter(user=user, is_active=True)
    ]


def _stored(user):
    raw = UserPreference.get_value(user, ACCOUNT_KEY)
    try:
        return json.loads(raw) if raw else None
    except ValueError:
        return None


def _store(user, values):
    UserPreference.objects.update_or_create(user=user, key=ACCOUNT_KEY, defaults={'value': json.dumps(values)})


def _initial(user, template):
    """The most common value of every channel across the user's courses; platform defaults otherwise."""
    votes = {}
    for preference in _course_preferences(user):
        for app, type_id, type_config, _ in _types(preference.notification_preference_config):
            for channel in CHANNELS:
                votes.setdefault((_key(app, type_id), channel), Counter())[type_config.get(channel)] += 1
    values = {}
    for app, type_id, type_config, _ in _types(template):
        key = _key(app, type_id)
        values[key] = {
            channel: (votes[(key, channel)].most_common(1)[0][0] if (key, channel) in votes else type_config.get(channel))
            for channel in CHANNELS
        }
    return values


def account_values(user):
    """{"app.type": {web, email, email_cadence}} — stored, built on the first call, new types from defaults."""
    template = _template()
    values = _stored(user)
    if values is None:
        values = _initial(user, template)
        _store(user, values)
    for app, type_id, type_config, _ in _types(template):
        values.setdefault(_key(app, type_id), {channel: type_config.get(channel) for channel in CHANNELS})
    return values


def account_config(user):
    """The stored settings in the shape of a course config (for the settings page)."""
    values = account_values(user)
    config = _template()
    for app, type_id, type_config, _ in _types(config):
        type_config.update(values[_key(app, type_id)])
    return config


def _apply(config, values, only_if=None):
    """Writes values into a course config; only_if(key, channel, course_value) limits what changes."""
    changed = False
    for app, type_id, type_config, locked in _types(config):
        wanted = values.get(_key(app, type_id))
        if not wanted:
            continue
        for channel in CHANNELS:
            if channel in locked or channel not in wanted or type_config.get(channel) == wanted[channel]:
                continue
            if only_if and not only_if(_key(app, type_id), channel, type_config.get(channel)):
                continue
            type_config[channel] = wanted[channel]
            changed = True
    return changed


def set_account_value(user, app, type_id, channel, value):
    """Changes one channel of the stored settings and the courses that still follow it."""
    if channel not in CHANNELS:
        raise ValueError(f'Unknown channel {channel}')
    values = account_values(user)
    key = _key(app, type_id)
    if key not in values:
        raise ValueError(f'Unknown notification type {key}')
    old = values[key].get(channel)
    values[key][channel] = value
    _store(user, values)
    updated = 0
    for preference in _course_preferences(user):
        config = copy.deepcopy(preference.notification_preference_config)
        follows = lambda k, c, course_value: k == key and c == channel and course_value == old  # noqa: E731
        if _apply(config, {key: {channel: value}}, only_if=follows):
            preference.notification_preference_config = config
            preference.save()
            updated += 1
    return updated


def _visible_config(user, preference):
    from openedx.core.djangoapps.notifications.utils import (  # pylint: disable=import-outside-toplevel
        filter_out_visible_preferences_by_course_ids,
    )
    config = copy.deepcopy(preference.notification_preference_config)
    filter_out_visible_preferences_by_course_ids(user, config, [preference.course_id])
    return config


def course_differs(user, preference, values=None):
    """True when a type the course shows differs from the stored settings (cadence only with email on)."""
    values = values or account_values(user)
    for app, type_id, type_config, locked in _types(_visible_config(user, preference)):
        if type_id == 'core' and not preference.notification_preference_config.get(app, {}).get(
                'core_notification_types'):
            continue
        wanted = values.get(_key(app, type_id))
        if not wanted:
            continue
        channels = ['web', 'email']
        if type_config.get('email') or wanted.get('email'):
            channels.append('email_cadence')
        if any(c not in locked and type_config.get(c) != wanted.get(c) for c in channels):
            return True
    return False


def customized_course_ids(user):
    values = account_values(user)
    return {preference.course_id for preference in _course_preferences(user) if course_differs(user, preference, values)}


def reset_courses(user, course_ids):
    """The stored settings back into these courses. Returns how many changed."""
    values = account_values(user)
    wanted = {str(course_id) for course_id in course_ids}
    changed = 0
    for preference in _course_preferences(user):
        if str(preference.course_id) not in wanted:
            continue
        config = copy.deepcopy(preference.notification_preference_config)
        if _apply(config, values):
            preference.notification_preference_config = config
            preference.save()
            changed += 1
    return changed


def set_all_off(user):
    """«Отключить все уведомления»: the stored settings off as well, so new courses start off."""
    values = account_values(user)
    for channels in values.values():
        channels['web'] = False
        channels['email'] = False
    _store(user, values)


@receiver(post_save, sender=CourseNotificationPreference, dispatch_uid='robbo_account_new_course_preference')
def new_course_starts_with_account_settings(sender, instance, created, **kwargs):  # pylint: disable=unused-argument
    """A new course preference (enrollment, joining a course team) takes the stored settings."""
    if not created:
        return
    values = _stored(instance.user)
    if not values:
        return
    config = copy.deepcopy(instance.notification_preference_config)
    if _apply(config, values):
        CourseNotificationPreference.objects.filter(pk=instance.pk).update(notification_preference_config=config)
        instance.notification_preference_config = config
