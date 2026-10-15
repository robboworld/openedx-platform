# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (course groups). See NOTICE at repository root.

"""Tests for group invite links: the /join/<code> page and the instructor dashboard API."""

from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.urls import reverse

from common.djangoapps.course_modes.models import CourseMode
from common.djangoapps.course_modes.tests.factories import CourseModeFactory
from common.djangoapps.student.models import CourseEnrollment
from common.djangoapps.student.tests.factories import TEST_PASSWORD, StaffFactory, UserFactory
from lms.djangoapps.robbo_groups import api
from lms.djangoapps.robbo_groups.models import GroupInvite
from lms.djangoapps.robbo_groups.views import JOIN_INTENT_SESSION_KEY
from openedx.core.djangoapps.course_groups.cohorts import add_cohort, add_user_to_cohort
from openedx.core.djangoapps.course_groups.models import CohortMembership, CourseCohort, CourseUserGroup
from openedx.core.djangoapps.course_groups.signals.signals import COHORT_MEMBERSHIP_UPDATED
from openedx.core.djangoapps.course_groups.tests.helpers import config_course_cohorts
from openedx.core.djangolib.testing.utils import skip_unless_lms
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory


class GroupInviteTestCase(ModuleStoreTestCase):
    """A cohorted course with free and paid modes, one group and its invite link."""

    def setUp(self):
        super().setUp()
        self.course = CourseFactory.create(display_name='Robotics 101')
        self.course_key = self.course.id
        CourseModeFactory.create(course_id=self.course_key, mode_slug=CourseMode.HONOR)
        CourseModeFactory.create(course_id=self.course_key, mode_slug=CourseMode.VERIFIED, min_price=1990)
        config_course_cohorts(self.course, is_cohorted=True)
        # Names no random token on the page (CSRF) can contain by chance.
        self.cohort = add_cohort(self.course_key, 'Class Five-B', CourseCohort.MANUAL)
        self.staff = StaffFactory(course_key=self.course_key)
        self.invite = api.issue_invite(self.cohort, self.staff)
        self.learner = UserFactory()

    def join_url(self, code=None):
        return reverse('robbo_groups:join', args=[code or self.invite.code])

    def assert_in_group(self, user, cohort, mode):
        enrollment = CourseEnrollment.get_enrollment(user, self.course_key)
        assert enrollment.is_active
        assert enrollment.mode == mode
        assert CohortMembership.objects.get(user=user, course_id=self.course_key).course_user_group == cohort


@skip_unless_lms
class JoinPageTests(GroupInviteTestCase):
    """/join/<code>"""

    def test_anonymous_sees_the_invitation(self):
        response = self.client.get(self.join_url())
        assert response.status_code == 200
        self.assertContains(response, 'Robotics 101')
        self.assertNotContains(response, 'Five-B')
        assert not CourseEnrollment.objects.filter(course_id=self.course_key).exists()

    def test_sign_up_remembers_the_invite_and_returns_to_it(self):
        response = self.client.post(self.join_url(), {'then': 'register'})
        target = urlparse(response['Location'])
        assert target.path == reverse('register_user')
        assert parse_qs(target.query)['next'] == [self.join_url()]
        assert self.client.session[JOIN_INTENT_SESSION_KEY] == self.invite.code

    def test_sign_in_goes_to_the_login_page(self):
        response = self.client.post(self.join_url(), {'then': 'login'})
        assert urlparse(response['Location']).path == reverse('signin_user')

    def test_back_from_sign_up_joins_without_another_click(self):
        self.client.post(self.join_url(), {'then': 'register'})
        self.client.login(username=self.learner.username, password=TEST_PASSWORD)

        response = self.client.get(self.join_url())

        assert response.status_code == 302
        assert str(self.course_key) in response['Location']
        self.assert_in_group(self.learner, self.cohort, CourseMode.HONOR)
        assert JOIN_INTENT_SESSION_KEY not in self.client.session

    def test_signed_in_learner_confirms_with_a_button(self):
        self.client.login(username=self.learner.username, password=TEST_PASSWORD)

        response = self.client.get(self.join_url())
        assert response.status_code == 200
        self.assertContains(response, self.learner.username)
        self.assertNotContains(response, 'Five-B')
        assert not CourseEnrollment.is_enrolled(self.learner, self.course_key)

        response = self.client.post(self.join_url())
        assert response.status_code == 302
        self.assert_in_group(self.learner, self.cohort, CourseMode.HONOR)

    def test_member_goes_straight_to_the_course(self):
        api.join_by_invite(self.learner, self.invite)
        self.client.login(username=self.learner.username, password=TEST_PASSWORD)

        response = self.client.get(self.join_url())

        assert response.status_code == 302
        assert str(self.course_key) in response['Location']

    def test_paid_enrollment_keeps_its_mode(self):
        CourseEnrollment.enroll(self.learner, self.course_key, mode=CourseMode.VERIFIED)
        self.client.login(username=self.learner.username, password=TEST_PASSWORD)

        self.client.post(self.join_url())

        self.assert_in_group(self.learner, self.cohort, CourseMode.VERIFIED)

    def test_placed_learner_stays_in_their_group(self):
        CourseEnrollment.enroll(self.learner, self.course_key, mode=CourseMode.HONOR)
        other = add_cohort(self.course_key, 'Class Five-A', CourseCohort.MANUAL)
        add_user_to_cohort(other, self.learner)
        self.client.login(username=self.learner.username, password=TEST_PASSWORD)

        response = self.client.get(self.join_url())
        assert response.status_code == 302
        assert str(self.course_key) in response['Location']

        response = self.client.post(self.join_url())
        assert response.status_code == 302
        self.assert_in_group(self.learner, other, CourseMode.HONOR)

    def test_placed_learner_stays_after_sign_in(self):
        other = add_cohort(self.course_key, 'Class Five-A', CourseCohort.MANUAL)
        add_user_to_cohort(other, self.learner)
        self.client.post(self.join_url(), {'then': 'login'})
        self.client.login(username=self.learner.username, password=TEST_PASSWORD)

        self.client.get(self.join_url())

        # was not enrolled: enrolled now, in the group the teacher chose
        self.assert_in_group(self.learner, other, CourseMode.HONOR)

    def test_group_joined_by_another_link_counts(self):
        other = add_cohort(self.course_key, 'Class Five-A', CourseCohort.RANDOM)
        api.join_by_invite(self.learner, api.issue_invite(other, self.staff))

        api.join_by_invite(self.learner, self.invite)

        self.assert_in_group(self.learner, other, CourseMode.HONOR)

    def test_automatic_group_does_not_count(self):
        CourseEnrollment.enroll(self.learner, self.course_key, mode=CourseMode.HONOR)
        default = add_cohort(self.course_key, 'Default Group', CourseCohort.RANDOM)
        add_user_to_cohort(default, self.learner)
        self.client.login(username=self.learner.username, password=TEST_PASSWORD)

        assert self.client.get(self.join_url()).status_code == 200
        self.client.post(self.join_url())

        self.assert_in_group(self.learner, self.cohort, CourseMode.HONOR)

    def test_code_is_case_insensitive(self):
        response = self.client.get(self.join_url(self.invite.code.upper()))
        assert response.status_code == 200

    def test_unknown_code(self):
        response = self.client.get(self.join_url('nosuchcode'))
        assert response.status_code == 404

    def test_switched_off_link(self):
        api.set_invite_active(self.invite, False, self.staff)
        self.client.login(username=self.learner.username, password=TEST_PASSWORD)

        response = self.client.post(self.join_url())

        assert response.status_code == 404
        assert not CourseEnrollment.is_enrolled(self.learner, self.course_key)

    def test_replaced_link_stops_working(self):
        old_code = self.invite.code
        api.issue_invite(self.cohort, self.staff)
        assert self.client.get(self.join_url(old_code)).status_code == 404

    def test_course_without_a_free_mode(self):
        CourseMode.objects.filter(course_id=self.course_key, mode_slug=CourseMode.HONOR).delete()
        self.client.login(username=self.learner.username, password=TEST_PASSWORD)

        response = self.client.post(self.join_url())

        assert response.status_code == 403
        assert not CourseEnrollment.is_enrolled(self.learner, self.course_key)


@skip_unless_lms
class CohortInviteApiTests(GroupInviteTestCase):
    """courses/<id>/cohorts/<cohort_id>/robbo-invite"""

    def api_url(self, cohort=None):
        return reverse('robbo_groups:cohort_invite', kwargs={
            'course_id': str(self.course_key), 'cohort_id': (cohort or self.cohort).id,
        })

    def test_learner_is_refused(self):
        self.client.login(username=self.learner.username, password=TEST_PASSWORD)
        assert self.client.get(self.api_url()).status_code == 403
        assert self.client.post(self.api_url(), {'action': 'issue'}).status_code == 403

    def test_group_without_a_link(self):
        cohort = add_cohort(self.course_key, '5C', CourseCohort.MANUAL)
        self.client.login(username=self.staff.username, password=TEST_PASSWORD)

        assert self.client.get(self.api_url(cohort)).json() == {'url': None, 'is_active': False}

    def test_issue_replace_and_switch(self):
        self.client.login(username=self.staff.username, password=TEST_PASSWORD)

        first = self.client.get(self.api_url()).json()
        assert first['is_active']
        assert first['url'].endswith(self.join_url())

        replaced = self.client.post(self.api_url(), {'action': 'issue'}).json()
        assert replaced['url'] != first['url']
        assert GroupInvite.objects.filter(cohort=self.cohort).count() == 1

        assert self.client.post(self.api_url(), {'action': 'disable'}).json()['is_active'] is False
        assert self.client.post(self.api_url(), {'action': 'enable'}).json()['is_active'] is True

    def test_unknown_action(self):
        self.client.login(username=self.staff.username, password=TEST_PASSWORD)
        assert self.client.post(self.api_url(), {'action': 'delete'}).status_code == 400

    def test_cohort_of_another_course(self):
        other_course = CourseFactory.create()
        other_cohort = add_cohort(other_course.id, 'X', CourseCohort.MANUAL)
        self.client.login(username=self.staff.username, password=TEST_PASSWORD)
        assert self.client.get(self.api_url(other_cohort)).status_code == 404


@skip_unless_lms
class CohortMembersApiTests(GroupInviteTestCase):
    """courses/<id>/cohorts/<cohort_id>/robbo-members"""

    def setUp(self):
        super().setUp()
        self.members = {}
        for username, name in (('vera', 'Vera Belova'), ('anna', 'Anna Zorina'), ('boris', '')):
            user = UserFactory(username=username, email=f'{username}@example.com', first_name='', last_name='')
            user.profile.name = name
            user.profile.save()
            CourseEnrollment.enroll(user, self.course_key, mode=CourseMode.HONOR)
            add_user_to_cohort(self.cohort, user)
            self.members[username] = user
        self.client.login(username=self.staff.username, password=TEST_PASSWORD)

    def api_url(self, cohort=None):
        return reverse('robbo_groups:cohort_members', kwargs={
            'course_id': str(self.course_key), 'cohort_id': (cohort or self.cohort).id,
        })

    def test_members_by_name(self):
        CourseEnrollment.unenroll(self.members['vera'], self.course_key)

        data = self.client.get(self.api_url()).json()

        assert data['count'] == 3
        assert data['has_more'] is False
        # no name: by username, first (an empty name sorts first)
        assert [m['username'] for m in data['members']] == ['boris', 'anna', 'vera']
        assert data['members'][1] == {
            'username': 'anna', 'email': 'anna@example.com', 'name': 'Anna Zorina',
            'is_enrolled': True, 'is_paid': False,
        }
        # left the course, still in the group
        assert data['members'][2]['is_enrolled'] is False

    def test_search_by_name_username_or_email(self):
        for query, expected in (('zorin', ['anna']), ('BORIS', ['boris']), ('vera@', ['vera']), ('nobody', [])):
            data = self.client.get(self.api_url(), {'q': query}).json()
            assert [m['username'] for m in data['members']] == expected, query

    def test_pages(self):
        with patch.object(api, 'MEMBERS_PAGE_SIZE', 2):
            first = self.client.get(self.api_url(), {'page': 1}).json()
            second = self.client.get(self.api_url(), {'page': 2}).json()
            past_the_end = self.client.get(self.api_url(), {'page': 3}).json()
        assert (len(first['members']), first['has_more']) == (2, True)
        assert (len(second['members']), second['has_more']) == (1, False)
        assert past_the_end['members'] == []

    def test_remove_to_the_default_group(self):
        response = self.client.post(self.api_url(), {'username': 'anna'})

        assert response.json() == {'removed': 'anna', 'new_group': 'Default Group'}
        default = CourseCohort.objects.get(
            course_user_group__course_id=self.course_key, assignment_type=CourseCohort.RANDOM,
        ).course_user_group
        self.assert_in_group(self.members['anna'], default, CourseMode.HONOR)
        assert self.client.get(self.api_url()).json()['count'] == 2

    def test_remove_to_an_existing_automatic_group(self):
        automatic = add_cohort(self.course_key, 'Everyone else', CourseCohort.RANDOM)

        response = self.client.post(self.api_url(), {'username': 'anna'})

        assert response.json()['new_group'] == 'Everyone else'
        self.assert_in_group(self.members['anna'], automatic, CourseMode.HONOR)

    def test_learner_who_left_the_course_is_not_placed(self):
        CourseEnrollment.unenroll(self.members['anna'], self.course_key)

        with patch.object(COHORT_MEMBERSHIP_UPDATED, 'send') as membership_updated:
            response = self.client.post(self.api_url(), {'username': 'anna'})

        membership_updated.assert_not_called()

        assert response.json()['new_group'] is None
        assert not CohortMembership.objects.filter(user=self.members['anna'], course_id=self.course_key).exists()

    def test_nobody_leaves_an_automatic_group(self):
        automatic = add_cohort(self.course_key, 'Everyone else', CourseCohort.RANDOM)
        add_user_to_cohort(automatic, self.members['anna'])
        url = reverse('robbo_groups:cohort_members', kwargs={
            'course_id': str(self.course_key), 'cohort_id': automatic.id,
        })

        assert self.client.post(url, {'username': 'anna'}).status_code == 400
        self.assert_in_group(self.members['anna'], automatic, CourseMode.HONOR)

    def test_removed_learner_can_be_placed_by_a_link_again(self):
        other = add_cohort(self.course_key, 'Class Five-A', CourseCohort.MANUAL)
        self.client.post(self.api_url(), {'username': 'anna'})

        api.join_by_invite(self.members['anna'], api.issue_invite(other, self.staff))

        self.assert_in_group(self.members['anna'], other, CourseMode.HONOR)

    def test_remove_someone_not_in_the_group(self):
        other = add_cohort(self.course_key, 'Class Five-A', CourseCohort.MANUAL)
        add_user_to_cohort(other, self.members['anna'])  # moved meanwhile

        assert self.client.post(self.api_url(), {'username': 'anna'}).status_code == 409
        assert self.client.post(self.api_url(), {'username': 'nosuchuser'}).status_code == 409
        self.assert_in_group(self.members['anna'], other, CourseMode.HONOR)

    def test_learner_is_refused(self):
        self.client.login(username=self.learner.username, password=TEST_PASSWORD)
        assert self.client.get(self.api_url()).status_code == 403
        assert self.client.post(self.api_url(), {'username': 'anna'}).status_code == 403
        assert CohortMembership.objects.filter(user=self.members['anna'], course_id=self.course_key).exists()

    def test_cohort_of_another_course(self):
        other_course = CourseFactory.create()
        other_cohort = add_cohort(other_course.id, 'X', CourseCohort.MANUAL)
        assert self.client.get(self.api_url(other_cohort)).status_code == 404

    def test_paid_member(self):
        CourseEnrollment.enroll(self.members['anna'], self.course_key, mode=CourseMode.VERIFIED)
        members = {m['username']: m for m in self.client.get(self.api_url()).json()['members']}
        assert members['anna']['is_paid'] is True
        assert members['vera']['is_paid'] is False

    def test_unenroll(self):
        with patch.object(COHORT_MEMBERSHIP_UPDATED, 'send') as membership_updated:
            response = self.client.post(self.api_url(), {'action': 'unenroll', 'username': 'anna'})

        assert response.json() == {'unenrolled': 'anna'}
        assert not CourseEnrollment.is_enrolled(self.members['anna'], self.course_key)
        assert not CohortMembership.objects.filter(user=self.members['anna'], course_id=self.course_key).exists()
        assert self.members['anna'] not in self.cohort.users.all()
        # its grade recalculation would put the learner into an automatic group again
        membership_updated.assert_not_called()

    def test_remove_recalculates_grades_of_an_enrolled_learner(self):
        with patch.object(COHORT_MEMBERSHIP_UPDATED, 'send') as membership_updated:
            self.client.post(self.api_url(), {'username': 'anna'})
        assert membership_updated.call_args_list[0].kwargs['user'] == self.members['anna']

    def test_unenrolled_learner_comes_back_by_a_link(self):
        other = add_cohort(self.course_key, 'Class Five-A', CourseCohort.MANUAL)
        self.client.post(self.api_url(), {'action': 'unenroll', 'username': 'anna'})

        api.join_by_invite(self.members['anna'], api.issue_invite(other, self.staff))

        self.assert_in_group(self.members['anna'], other, CourseMode.HONOR)

    def test_unenroll_from_an_automatic_group(self):
        automatic = add_cohort(self.course_key, 'Everyone else', CourseCohort.RANDOM)
        add_user_to_cohort(automatic, self.members['anna'])

        response = self.client.post(self.api_url(automatic), {'action': 'unenroll', 'username': 'anna'})

        assert response.status_code == 200
        assert not CourseEnrollment.is_enrolled(self.members['anna'], self.course_key)

    def test_unenroll_someone_not_in_the_group(self):
        other = add_cohort(self.course_key, 'Class Five-A', CourseCohort.MANUAL)
        add_user_to_cohort(other, self.members['anna'])

        assert self.client.post(self.api_url(), {'action': 'unenroll', 'username': 'anna'}).status_code == 409
        assert CourseEnrollment.is_enrolled(self.members['anna'], self.course_key)

    def test_unknown_action(self):
        assert self.client.post(self.api_url(), {'action': 'ban', 'username': 'anna'}).status_code == 400


@skip_unless_lms
class CohortDeleteApiTests(GroupInviteTestCase):
    """courses/<id>/cohorts/<cohort_id>/robbo-delete"""

    def setUp(self):
        super().setUp()
        self.enrolled = UserFactory()
        CourseEnrollment.enroll(self.enrolled, self.course_key, mode=CourseMode.HONOR)
        add_user_to_cohort(self.cohort, self.enrolled)
        self.left = UserFactory()  # left the course, still in the group
        add_user_to_cohort(self.cohort, self.left)
        self.client.login(username=self.staff.username, password=TEST_PASSWORD)

    def delete_url(self, cohort=None):
        return reverse('robbo_groups:cohort_delete', kwargs={
            'course_id': str(self.course_key), 'cohort_id': (cohort or self.cohort).id,
        })

    def test_delete(self):
        response = self.client.post(self.delete_url())

        assert response.json() == {'deleted': 'Class Five-B', 'new_groups': ['Default Group']}
        assert not CourseUserGroup.objects.filter(id=self.cohort.id).exists()
        assert not GroupInvite.objects.filter(code=self.invite.code).exists()
        default = CohortMembership.objects.get(user=self.enrolled, course_id=self.course_key).course_user_group
        assert default.name == 'Default Group'
        assert CourseEnrollment.is_enrolled(self.enrolled, self.course_key)
        assert not CohortMembership.objects.filter(user=self.left, course_id=self.course_key).exists()

    def test_link_of_a_deleted_group(self):
        code = self.invite.code
        self.client.post(self.delete_url())
        assert self.client.get(self.join_url(code)).status_code == 404

    def test_get_is_not_allowed(self):
        assert self.client.get(self.delete_url()).status_code == 405

    def test_learner_is_refused(self):
        self.client.login(username=self.learner.username, password=TEST_PASSWORD)
        assert self.client.post(self.delete_url()).status_code == 403
        assert CourseUserGroup.objects.filter(id=self.cohort.id).exists()

    def test_default_group_is_not_deleted(self):
        default = add_cohort(self.course_key, 'Default Group', CourseCohort.RANDOM)

        assert self.client.post(self.delete_url(default)).json() == {'error': 'default group'}
        assert CourseUserGroup.objects.filter(id=default.id).exists()

    def test_one_of_several_automatic_groups_is_deleted(self):
        first = add_cohort(self.course_key, 'Default Group', CourseCohort.RANDOM)
        second = add_cohort(self.course_key, 'Everyone else', CourseCohort.RANDOM)
        add_user_to_cohort(first, self.enrolled)

        response = self.client.post(self.delete_url(first))

        assert response.json() == {'deleted': 'Default Group', 'new_groups': ['Everyone else']}
        self.assert_in_group(self.enrolled, second, CourseMode.HONOR)
