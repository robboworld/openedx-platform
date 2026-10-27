# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution. See NOTICE at repository root.
"""Service API for the LK server (service_api.py)."""
from datetime import timedelta

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from edx_toggles.toggles.testutils import override_waffle_flag
from rest_framework.test import APITestCase

from common.djangoapps.student.tests.factories import UserFactory
from openedx.core.djangoapps.notifications.config.waffle import ENABLE_NOTIFICATIONS
from openedx.core.djangoapps.notifications.models import Notification
from openedx.core.djangoapps.oauth_dispatch.tests.factories import AccessTokenFactory, ApplicationFactory

COURSE = 'course-v1:Org+Num+Run'


@override_settings(ROBBO_NOTIFICATIONS_SERVICE_USERS=['lk_service'], LMS_ROOT_URL='https://lms.example')
@override_waffle_flag(ENABLE_NOTIFICATIONS, active=True)
class ServiceApiTest(APITestCase):

    def setUp(self):
        super().setUp()
        self.service = UserFactory(username='lk_service')
        self.learner = UserFactory()
        self.other = UserFactory()
        self.notes = [self.note(self.learner, minutes) for minutes in (30, 20, 10)]
        self.foreign = self.note(self.other, 5)

    def note(self, user, minutes_ago):
        notification = Notification.objects.create(
            user=user, course_id=COURSE, app_name='grading', notification_type='ora_grade_assigned',
            content_context={'ora_name': 'Проект', 'points_earned': 4, 'points_possible': 5, 'course_name': 'Курс'},
            content_url='/courses/x/jump_to/y',
        )
        Notification.objects.filter(id=notification.id).update(created=timezone.now() - timedelta(minutes=minutes_ago))
        return Notification.objects.get(id=notification.id)

    def auth(self, user):
        token = AccessTokenFactory(user=user, application=ApplicationFactory(user=user))
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.token}')

    def test_only_service_users(self):
        url = reverse('robbo_notifications:service_unread_count')
        self.assertEqual(self.client.get(url, {'user_id': self.learner.id}).status_code, 401)
        self.auth(self.learner)
        self.assertEqual(self.client.get(url, {'user_id': self.learner.id}).status_code, 403)

    @override_settings(ROBBO_NOTIFICATIONS_SERVICE_USERS=[])
    def test_off_without_setting(self):
        self.auth(self.service)
        response = self.client.get(reverse('robbo_notifications:service_unread_count'), {'user_id': self.learner.id})
        self.assertEqual(response.status_code, 403)

    def test_feed_texts_and_pages(self):
        self.auth(self.service)
        url = reverse('robbo_notifications:service_feed')
        first = self.client.get(url, {'user_id': self.learner.id, 'limit': 2, 'lang': 'ru'}).json()
        self.assertTrue(first['enabled'])
        self.assertEqual([item['id'] for item in first['items']], [self.notes[2].id, self.notes[1].id])
        item = first['items'][0]
        self.assertEqual(item['text'], 'Ваш ответ на задание Проект проверен: 4 из 5 баллов')
        self.assertEqual(item['label'], 'Задание проверено')
        self.assertEqual(item['url'], 'https://lms.example/courses/x/jump_to/y')
        self.assertEqual(item['course_name'], 'Курс')
        self.assertFalse(item['read'])
        self.assertIsNone(item['read_at'])
        self.assertTrue(first['links']['feed'].endswith('/notifications'))
        second = self.client.get(url, {'user_id': self.learner.id, 'limit': 2, 'before': first['next_before']}).json()
        self.assertEqual([item['id'] for item in second['items']], [self.notes[0].id])
        self.assertIsNone(second['next_before'])

    def test_unknown_user(self):
        self.auth(self.service)
        response = self.client.get(reverse('robbo_notifications:service_feed'), {'user_id': 999999})
        self.assertEqual(response.status_code, 404)

    def test_read_ids_and_all(self):
        self.auth(self.service)
        count_url = reverse('robbo_notifications:service_unread_count')
        read_url = reverse('robbo_notifications:service_read')
        self.assertEqual(self.client.get(count_url, {'user_id': self.learner.id}).json()['unread'], 3)
        # Another user's id in the list is ignored.
        response = self.client.post(read_url, {'user_id': self.learner.id, 'ids': [self.notes[0].id, self.foreign.id]},
                                    format='json')
        self.assertEqual(response.json(), {'read': 1})
        self.assertIsNone(Notification.objects.get(id=self.foreign.id).last_read)
        self.assertEqual(self.client.get(count_url, {'user_id': self.learner.id}).json()['unread'], 2)
        response = self.client.post(read_url, {'user_id': self.learner.id, 'all': True}, format='json')
        self.assertEqual(response.json(), {'read': 2})
        counts = self.client.get(count_url, {'user_id': self.learner.id}).json()
        self.assertEqual((counts['unread'], counts['unseen']), (0, 0))
        bad = self.client.post(read_url, {'user_id': self.learner.id, 'ids': 'x'}, format='json')
        self.assertEqual(bad.status_code, 400)

    @override_waffle_flag(ENABLE_NOTIFICATIONS, active=False)
    def test_disabled(self):
        self.auth(self.service)
        response = self.client.get(reverse('robbo_notifications:service_feed'), {'user_id': self.learner.id}).json()
        self.assertEqual((response['enabled'], response['items'], response['next_before']), (False, [], None))
