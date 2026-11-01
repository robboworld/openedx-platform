# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution. See NOTICE at repository root.

"""Robbo: a notification type added later and the stored settings «Для всех курсов» (robbo_account.py)."""

import json

from django.test import TestCase
from opaque_keys.edx.keys import CourseKey

from common.djangoapps.student.tests.factories import UserFactory
from openedx.core.djangoapps.notifications import robbo_account
from openedx.core.djangoapps.notifications.base_notification import NotificationAppManager
from openedx.core.djangoapps.notifications.email import ONE_CLICK_EMAIL_UNSUB_KEY
from openedx.core.djangoapps.notifications.models import (
    CourseNotificationPreference,
    get_course_notification_preference_config_version,
)
from openedx.core.djangoapps.user_api.models import UserPreference

APP, NEW_TYPE = 'learning', 'learner_certificate_offer'  # on for the site and email by default
KEY = f'{APP}.{NEW_TYPE}'
COURSE = CourseKey.from_string('course-v1:Robbo+New+2026')
OTHER_COURSE = CourseKey.from_string('course-v1:Robbo+Other+2026')


def _old_config():
    """The course config of the previous version: the platform did not have NEW_TYPE yet."""
    config = NotificationAppManager().get_notification_app_preferences()
    del config[APP]['notification_types'][NEW_TYPE]
    return config


def _values(config, on):
    """Stored settings «Для всех курсов» for every type of ``config``: all on, or all off («Отключить все»)."""
    return {
        f'{app}.{type_id}': {'web': on, 'email': on, 'email_cadence': type_config.get('email_cadence')}
        for app, app_config in config.items()
        for type_id, type_config in app_config['notification_types'].items()
    }


class NewTypeFollowsAccountTests(TestCase):
    """A type added in a new config version starts as the user's stored settings say, not as the defaults."""

    def setUp(self):
        super().setUp()
        self.user = UserFactory.create()
        # Course settings saved before the new type existed
        CourseNotificationPreference.objects.create(
            user=self.user, course_id=COURSE, notification_preference_config=_old_config(),
            config_version=get_course_notification_preference_config_version() - 1,
        )

    def _store(self, on):
        UserPreference.objects.create(user=self.user, key=robbo_account.ACCOUNT_KEY,
                                      value=json.dumps(_values(_old_config(), on)))

    def _course_channels(self, course=COURSE):
        preference = CourseNotificationPreference.get_user_course_preference(self.user.id, course)
        assert preference.config_version == get_course_notification_preference_config_version()
        channels = preference.notification_preference_config[APP]['notification_types'][NEW_TYPE]
        return channels['web'], channels['email']

    def test_all_off_keeps_the_new_type_off(self):
        self._store(on=False)
        assert self._course_channels() == (False, False)
        stored = json.loads(UserPreference.get_value(self.user, robbo_account.ACCOUNT_KEY))
        assert (stored[KEY]['web'], stored[KEY]['email']) == (False, False)
        assert robbo_account.all_off(self.user)

    def test_all_off_through_the_bulk_update(self):
        self._store(on=False)
        preference = CourseNotificationPreference.get_user_notification_preferences(self.user).get(course_id=COURSE)
        preference.refresh_from_db()
        channels = preference.notification_preference_config[APP]['notification_types'][NEW_TYPE]
        assert (channels['web'], channels['email']) == (False, False)

    def test_all_off_and_a_course_joined_later(self):
        self._store(on=False)
        assert self._course_channels(OTHER_COURSE) == (False, False)

    def test_something_on_gets_the_defaults(self):
        self._store(on=True)
        assert self._course_channels() == (True, True)
        assert not robbo_account.all_off(self.user)

    def test_no_stored_settings_gets_the_defaults(self):
        assert self._course_channels() == (True, True)

    def test_one_click_unsubscribe_never_turns_email_on(self):
        self._store(on=True)
        UserPreference.objects.create(user=self.user, key=ONE_CLICK_EMAIL_UNSUB_KEY, value='true')
        preference = CourseNotificationPreference.get_user_notification_preferences(self.user).get(course_id=COURSE)
        preference.refresh_from_db()
        channels = preference.notification_preference_config[APP]['notification_types'][NEW_TYPE]
        assert (channels['web'], channels['email']) == (True, False)

    def test_known_types_keep_the_course_value(self):
        # A course with its own value on a type that already existed keeps it
        self._store(on=False)
        preference = CourseNotificationPreference.objects.get(user=self.user, course_id=COURSE)
        config = preference.notification_preference_config
        config[APP]['notification_types']['learner_grade_changed']['web'] = True
        preference.notification_preference_config = config
        preference.save()
        preference = CourseNotificationPreference.get_user_course_preference(self.user.id, COURSE)
        assert preference.notification_preference_config[APP]['notification_types']['learner_grade_changed']['web']
