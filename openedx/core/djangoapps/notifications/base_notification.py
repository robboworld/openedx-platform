"""
Base setup for Notification Apps and Types.
"""
from django.utils.translation import gettext_lazy as _

from .email_notifications import EmailCadence
from common.djangoapps.student.roles import CourseInstructorRole, CourseLimitedStaffRole, CourseStaffRole
from .utils import find_app_in_normalized_apps, find_pref_in_normalized_prefs
from ..django_comment_common.models import FORUM_ROLE_ADMINISTRATOR, FORUM_ROLE_MODERATOR, FORUM_ROLE_COMMUNITY_TA
from .notification_content import get_notification_type_context_function

FILTER_AUDIT_EXPIRED_USERS_WITH_NO_ROLE = 'filter_audit_expired_users_with_no_role'

COURSE_NOTIFICATION_TYPES = {
    'new_comment_on_response': {
        'notification_app': 'discussion',
        'name': 'new_comment_on_response',
        'is_core': True,
        'content_template': _('<{p}><{strong}>{replier_name}</{strong}> commented on your response to the post '
                              '<{strong}>{post_title}</{strong}></{p}>'),
        'content_context': {
            'post_title': 'Post title',
            'replier_name': 'replier name',
        },
        'email_template': '',
        'filters': [FILTER_AUDIT_EXPIRED_USERS_WITH_NO_ROLE]
    },
    'new_comment': {
        'notification_app': 'discussion',
        'name': 'new_comment',
        'is_core': True,
        'content_template': _('<{p}><{strong}>{replier_name}</{strong}> commented on <{strong}>{author_name}'
                              '</{strong}> response to your post <{strong}>{post_title}</{strong}></{p}>'),
        'content_context': {
            'post_title': 'Post title',
            'author_name': 'author name',
            'replier_name': 'replier name',
        },
        'email_template': '',
        'filters': [FILTER_AUDIT_EXPIRED_USERS_WITH_NO_ROLE]
    },
    'new_response': {
        'notification_app': 'discussion',
        'name': 'new_response',
        'is_core': True,
        'content_template': _('<{p}><{strong}>{replier_name}</{strong}> responded to your '
                              'post <{strong}>{post_title}</{strong}></{p}>'),
        'content_context': {
            'post_title': 'Post title',
            'replier_name': 'replier name',
        },
        'email_template': '',
        'filters': [FILTER_AUDIT_EXPIRED_USERS_WITH_NO_ROLE]
    },
    'new_discussion_post': {
        'notification_app': 'discussion',
        'name': 'new_discussion_post',
        'is_core': False,
        'info': '',
        'web': False,
        'email': False,
        'email_cadence': EmailCadence.DAILY,
        'push': False,
        'non_editable': [],
        'content_template': _('<{p}><{strong}>{username}</{strong}> posted <{strong}>{post_title}</{strong}></{p}>'),
        'grouped_content_template': _('<{p}><{strong}>{replier_name}</{strong}> and others started new discussions'
                                      '</{p}>'),
        'content_context': {
            'post_title': 'Post title',
            'username': 'Post author name',
        },
        'email_template': '',
        'filters': [FILTER_AUDIT_EXPIRED_USERS_WITH_NO_ROLE]
    },
    'new_question_post': {
        'notification_app': 'discussion',
        'name': 'new_question_post',
        'is_core': False,
        'info': '',
        'web': False,
        'email': False,
        'email_cadence': EmailCadence.DAILY,
        'push': False,
        'non_editable': [],
        'content_template': _('<{p}><{strong}>{username}</{strong}> asked <{strong}>{post_title}</{strong}></{p}>'),
        'content_context': {
            'post_title': 'Post title',
            'username': 'Post author name',
        },
        'email_template': '',
        'filters': [FILTER_AUDIT_EXPIRED_USERS_WITH_NO_ROLE]
    },
    'response_on_followed_post': {
        'notification_app': 'discussion',
        'name': 'response_on_followed_post',
        'is_core': True,
        'info': '',
        'non_editable': [],
        'content_template': _('<{p}><{strong}>{replier_name}</{strong}> responded to a post you’re following: '
                              '<{strong}>{post_title}</{strong}></{p}>'),
        'content_context': {
            'post_title': 'Post title',
            'replier_name': 'replier name',
        },
        'email_template': '',
        'filters': [FILTER_AUDIT_EXPIRED_USERS_WITH_NO_ROLE]
    },
    'comment_on_followed_post': {
        'notification_app': 'discussion',
        'name': 'comment_on_followed_post',
        'is_core': True,
        'info': '',
        'non_editable': [],
        'content_template': _('<{p}><{strong}>{replier_name}</{strong}> commented on <{strong}>{author_name}'
                              '</{strong}> response in a post you’re following <{strong}>{post_title}'
                              '</{strong}></{p}>'),
        'content_context': {
            'post_title': 'Post title',
            'author_name': 'author name',
            'replier_name': 'replier name',
        },
        'email_template': '',
        'filters': [FILTER_AUDIT_EXPIRED_USERS_WITH_NO_ROLE]
    },
    'content_reported': {
        'notification_app': 'discussion',
        'name': 'content_reported',
        'is_core': False,
        'info': '',
        'web': True,
        'email': True,
        'email_cadence': EmailCadence.DAILY,
        'push': True,
        'non_editable': [],
        'content_template': _('<p><strong>{username}’s </strong> {content_type} has been reported <strong> {'
                              'content}</strong></p>'),

        'content_context': {
            'post_title': 'Post title',
            'author_name': 'author name',
            'replier_name': 'replier name',
        },
        'email_template': '',
        'visible_to': [FORUM_ROLE_ADMINISTRATOR, FORUM_ROLE_MODERATOR, FORUM_ROLE_COMMUNITY_TA]
    },
    'response_endorsed_on_thread': {
        'notification_app': 'discussion',
        'name': 'response_endorsed_on_thread',
        'is_core': True,
        'info': '',
        'non_editable': [],
        'content_template': _('<{p}><{strong}>{replier_name}\'s</{strong}> response has been endorsed in your post '
                              '<{strong}>{post_title}</{strong}></{p}>'),
        'content_context': {
            'post_title': 'Post title',
            'replier_name': 'replier name',
        },
        'email_template': '',
        'filters': [FILTER_AUDIT_EXPIRED_USERS_WITH_NO_ROLE]
    },
    'response_endorsed': {
        'notification_app': 'discussion',
        'name': 'response_endorsed',
        'is_core': True,
        'info': '',
        'non_editable': [],
        'content_template': _('<{p}>Your response has been endorsed on the post <{strong}>{post_title}</{strong}></{'
                              'p}>'),
        'content_context': {
            'post_title': 'Post title',
        },
        'email_template': '',
        'filters': [FILTER_AUDIT_EXPIRED_USERS_WITH_NO_ROLE]
    },
    'course_updates': {
        'notification_app': 'updates',
        'name': 'course_updates',
        'is_core': False,
        'info': '',
        'web': True,
        'email': False,
        'push': True,
        'email_cadence': EmailCadence.DAILY,
        'non_editable': [],
        'content_template': _('<{p}><{strong}>{course_update_content}</{strong}></{p}>'),
        'content_context': {
            'course_update_content': 'Course update',
        },
        'email_template': '',
        'filters': [FILTER_AUDIT_EXPIRED_USERS_WITH_NO_ROLE]
    },
    'ora_staff_notifications': {
        'notification_app': 'grading',
        'name': 'ora_staff_notifications',
        'is_core': False,
        'info': 'Notifications for when a submission is made for ORA that includes staff grading step.',
        'web': True,
        'email': False,
        'push': False,
        'email_cadence': EmailCadence.DAILY,
        'non_editable': [],
        'content_template': _('<{p}>You have a new open response submission awaiting review for '
                              '<{strong}>{ora_name}</{strong}></{p}>'),
        'grouped_content_template': _('<{p}>You have multiple submissions awaiting review for '
                                      '<{strong}>{ora_name}</{strong}></{p}>'),
        'content_context': {
            'ora_name': 'Name of ORA in course',
        },
        'email_template': '',
        'filters': [FILTER_AUDIT_EXPIRED_USERS_WITH_NO_ROLE],
        'visible_to': [CourseStaffRole.ROLE, CourseInstructorRole.ROLE]
    },
    'ora_grade_assigned': {
        'notification_app': 'grading',
        'name': 'ora_grade_assigned',
        'is_core': False,
        'info': '',
        'web': True,
        'email': False,  # Robbo: off by default (the ROBBO default preset, 2026-10-23)
        'push': False,
        'email_cadence': EmailCadence.DAILY,
        'non_editable': [],
        'content_template': _('<{p}>You have received {points_earned} out of {points_possible} on your assessment: '
                              '<{strong}>{ora_name}</{strong}></{p}>'),
        'content_context': {
            'ora_name': 'Name of ORA in course',
            'points_earned': 'Points earned',
            'points_possible': 'Points possible',
        },
        'email_template': '',
        'filters': [FILTER_AUDIT_EXPIRED_USERS_WITH_NO_ROLE],
    },
    # Robbo: learner progress for the course team (robbo_progress.py sends them; texts for the
    # site, panel and emails are built from content_context, see robbo_texts.py and the MFE feed).
    'learner_test_completed': {
        'notification_app': 'learner_progress',
        'name': 'learner_test_completed',
        'is_core': False,
        'info': 'A learner answered every problem of a graded subsection.',
        'web': False,  # Robbo: off by default (the ROBBO default preset, 2026-10-23)
        'email': False,
        'push': False,
        'email_cadence': EmailCadence.DAILY,
        'non_editable': [],
        'content_template': _('<{p}><{strong}>{learner_name}</{strong}> completed the test '
                              '<{strong}>{test_name}</{strong}>: {points_earned} of {points_possible}</{p}>'),
        'content_context': {
            'learner_name': 'Name of the learner',
            'test_name': 'Name of the graded subsection',
            'points_earned': 'Points earned',
            'points_possible': 'Points possible',
        },
        'email_template': '',
        'filters': [],
        'visible_to': [CourseStaffRole.ROLE, CourseInstructorRole.ROLE, CourseLimitedStaffRole.ROLE],
    },
    'learner_all_tests_completed': {
        'notification_app': 'learner_progress',
        'name': 'learner_all_tests_completed',
        'is_core': False,
        'info': '',
        'web': True,
        'email': False,
        'push': False,
        'email_cadence': EmailCadence.DAILY,
        'non_editable': [],
        'content_template': _('<{p}><{strong}>{learner_name}</{strong}> completed all {count} tests</{p}>'),
        'content_context': {
            'learner_name': 'Name of the learner',
            'count': 'Number of graded subsections',
        },
        'email_template': '',
        'filters': [],
        'visible_to': [CourseStaffRole.ROLE, CourseInstructorRole.ROLE, CourseLimitedStaffRole.ROLE],
    },
    'learner_ora_submitted': {
        'notification_app': 'learner_progress',
        'name': 'learner_ora_submitted',
        'is_core': False,
        'info': 'A learner sent an answer to an open response assignment.',
        'web': True,
        'email': False,
        'push': False,
        'email_cadence': EmailCadence.DAILY,
        'non_editable': [],
        'content_template': _('<{p}><{strong}>{learner_name}</{strong}> submitted '
                              '<{strong}>{ora_name}</{strong}></{p}>'),
        'content_context': {
            'learner_name': 'Name of the learner',
            'ora_name': 'Name of the open response assignment',
        },
        'email_template': '',
        'filters': [],
        'visible_to': [CourseStaffRole.ROLE, CourseInstructorRole.ROLE, CourseLimitedStaffRole.ROLE],
    },
    'learner_all_ora_submitted': {
        'notification_app': 'learner_progress',
        'name': 'learner_all_ora_submitted',
        'is_core': False,
        'info': '',
        'web': True,
        'email': False,
        'push': False,
        'email_cadence': EmailCadence.DAILY,
        'non_editable': [],
        'content_template': _('<{p}><{strong}>{learner_name}</{strong}> submitted all {count} '
                              'open response assignments</{p}>'),
        'content_context': {
            'learner_name': 'Name of the learner',
            'count': 'Number of open response assignments',
        },
        'email_template': '',
        'filters': [],
        'visible_to': [CourseStaffRole.ROLE, CourseInstructorRole.ROLE, CourseLimitedStaffRole.ROLE],
    },
    'learner_course_completed': {
        'notification_app': 'learner_progress',
        'name': 'learner_course_completed',
        'is_core': False,
        'info': 'Sent instead of the two above when the last test or assignment closes the course.',
        'web': True,
        'email': False,
        'push': False,
        'email_cadence': EmailCadence.DAILY,
        'non_editable': [],
        'content_template': _('<{p}><{strong}>{learner_name}</{strong}> completed all tests and '
                              'open response assignments</{p}>'),
        'content_context': {
            'learner_name': 'Name of the learner',
        },
        'email_template': '',
        'filters': [],
        'visible_to': [CourseStaffRole.ROLE, CourseInstructorRole.ROLE, CourseLimitedStaffRole.ROLE],
    },
    # Robbo: more notifications (robbo_events.py — events, robbo_scheduled.py — by schedule). Texts for
    # the site, panel and emails come from robbo_texts.py and the MFE; these templates are the stock fallback.
    'learner_deadline_soon': {
        'notification_app': 'learning',
        'name': 'learner_deadline_soon',
        'is_core': False,
        'info': '',
        'web': True,
        'email': False,
        'push': False,
        'email_cadence': EmailCadence.DAILY,
        'non_editable': [],
        'content_template': _('<{p}>The deadline for <{strong}>{block_name}</{strong}> is {due_text}</{p}>'),
        'content_context': {
            'block_name': 'block_name',
            'due_text': 'due_text',
        },
        'email_template': '',
        'filters': [],
    },
    'learner_section_released': {
        'notification_app': 'learning',
        'name': 'learner_section_released',
        'is_core': False,
        'info': '',
        'web': True,
        'email': False,
        'push': False,
        'email_cadence': EmailCadence.DAILY,
        'non_editable': [],
        'content_template': _('<{p}>A new section is open: <{strong}>{section_name}</{strong}></{p}>'),
        'content_context': {
            'section_name': 'section_name',
        },
        'email_template': '',
        'filters': [],
    },
    'learner_certificate_issued': {
        'notification_app': 'learning',
        'name': 'learner_certificate_issued',
        'is_core': False,
        'info': '',
        'web': True,
        'email': False,
        'push': False,
        'email_cadence': EmailCadence.DAILY,
        'non_editable': [],
        'content_template': _('<{p}>Your certificate for <{strong}>{course_name}</{strong}> is ready</{p}>'),
        'content_context': {
            'course_name': 'course_name',
        },
        'email_template': '',
        'filters': [],
    },
    # Robbo: passed a course whose certificate is sold (robbo_certificates/notifications.py); once per
    # learner and course, so the letter goes right away.
    'learner_certificate_offer': {
        'notification_app': 'learning',
        'name': 'learner_certificate_offer',
        'is_core': False,
        'info': '',
        'web': True,
        'email': True,
        'push': False,
        'email_cadence': EmailCadence.IMMEDIATELY,
        'non_editable': [],
        'content_template': _('<{p}>You passed <{strong}>{course_name}</{strong}>: the certificate is available '
                              'for {price_display}</{p}>'),
        'content_context': {
            'course_name': 'course_name',
            'price_display': 'price_display',
        },
        'email_template': '',
        'filters': [],
    },
    'learner_grade_changed': {
        'notification_app': 'learning',
        'name': 'learner_grade_changed',
        'is_core': False,
        'info': '',
        'web': True,
        'email': False,
        'push': False,
        'email_cadence': EmailCadence.DAILY,
        'non_editable': [],
        'content_template': _('<{p}>Your grade for <{strong}>{item_name}</{strong}> was changed: {points_earned} of {points_possible}</{p}>'),
        'content_context': {
            'item_name': 'item_name',
            'points_earned': 'points_earned',
            'points_possible': 'points_possible',
        },
        'email_template': '',
        'filters': [],
    },
    'learner_added_to_course': {
        'notification_app': 'learning',
        'name': 'learner_added_to_course',
        'is_core': False,
        'info': '',
        'web': True,
        'email': False,
        'push': False,
        'email_cadence': EmailCadence.DAILY,
        'non_editable': [],
        'content_template': _('<{p}>You were enrolled in <{strong}>{course_name}</{strong}></{p}>'),
        'content_context': {
            'course_name': 'course_name',
        },
        'email_template': '',
        'filters': [],
    },
    'learner_enrolled': {
        'notification_app': 'learner_progress',
        'name': 'learner_enrolled',
        'is_core': False,
        'info': '',
        'web': False,  # Robbo: off by default (the ROBBO default preset, 2026-10-23)
        'email': False,
        'push': False,
        'email_cadence': EmailCadence.DAILY,
        'non_editable': [],
        'content_template': _('<{p}><{strong}>{learner_name}</{strong}> enrolled in the course</{p}>'),
        'content_context': {
            'learner_name': 'learner_name',
        },
        'email_template': '',
        'filters': [],
        'visible_to': [CourseStaffRole.ROLE, CourseInstructorRole.ROLE, CourseLimitedStaffRole.ROLE],
    },
    'learner_unenrolled': {
        'notification_app': 'learner_progress',
        'name': 'learner_unenrolled',
        'is_core': False,
        'info': '',
        'web': False,  # Robbo: off by default (the ROBBO default preset, 2026-10-23)
        'email': False,
        'push': False,
        'email_cadence': EmailCadence.DAILY,
        'non_editable': [],
        'content_template': _('<{p}><{strong}>{learner_name}</{strong}> left the course</{p}>'),
        'content_context': {
            'learner_name': 'learner_name',
        },
        'email_template': '',
        'filters': [],
        'visible_to': [CourseStaffRole.ROLE, CourseInstructorRole.ROLE, CourseLimitedStaffRole.ROLE],
    },
    'learner_low_score': {
        'notification_app': 'learner_progress',
        'name': 'learner_low_score',
        'is_core': False,
        'info': '',
        'web': False,  # Robbo: off by default (the ROBBO default preset, 2026-10-23)
        'email': False,
        'push': False,
        'email_cadence': EmailCadence.DAILY,
        'non_editable': [],
        'content_template': _('<{p}><{strong}>{learner_name}</{strong}> scored {points_earned} of {points_possible} on <{strong}>{test_name}</{strong}></{p}>'),
        'content_context': {
            'learner_name': 'learner_name',
            'test_name': 'test_name',
            'points_earned': 'points_earned',
            'points_possible': 'points_possible',
        },
        'email_template': '',
        'filters': [],
        'visible_to': [CourseStaffRole.ROLE, CourseInstructorRole.ROLE, CourseLimitedStaffRole.ROLE],
    },
    'learner_missed_deadline': {
        'notification_app': 'learner_progress',
        'name': 'learner_missed_deadline',
        'is_core': False,
        'info': '',
        'web': True,
        'email': False,
        'push': False,
        'email_cadence': EmailCadence.DAILY,
        'non_editable': [],
        'content_template': _('<{p}><{strong}>{learner_name}</{strong}> missed the deadline for <{strong}>{block_name}</{strong}></{p}>'),
        'content_context': {
            'learner_name': 'learner_name',
            'block_name': 'block_name',
        },
        'email_template': '',
        'filters': [],
        'visible_to': [CourseStaffRole.ROLE, CourseInstructorRole.ROLE, CourseLimitedStaffRole.ROLE],
    },
    'learner_inactive': {
        'notification_app': 'learner_progress',
        'name': 'learner_inactive',
        'is_core': False,
        'info': '',
        'web': False,  # Robbo: off by default (the ROBBO default preset, 2026-10-23)
        'email': False,
        'push': False,
        'email_cadence': EmailCadence.DAILY,
        'non_editable': [],
        'content_template': _('<{p}><{strong}>{learner_name}</{strong}> has not been active for {days} days</{p}>'),
        'content_context': {
            'learner_name': 'learner_name',
            'days': 'days',
        },
        'email_template': '',
        'filters': [],
        'visible_to': [CourseStaffRole.ROLE, CourseInstructorRole.ROLE, CourseLimitedStaffRole.ROLE],
    },
    'submission_review_overdue': {
        'notification_app': 'learner_progress',
        'name': 'submission_review_overdue',
        'is_core': False,
        'info': '',
        'web': True,
        'email': False,
        'push': False,
        'email_cadence': EmailCadence.DAILY,
        'non_editable': [],
        'content_template': _('<{p}>The answer of <{strong}>{learner_name}</{strong}> to <{strong}>{ora_name}</{strong}> has been waiting for review for {days} days</{p}>'),
        'content_context': {
            'learner_name': 'learner_name',
            'ora_name': 'ora_name',
            'days': 'days',
        },
        'email_template': '',
        'filters': [],
        'visible_to': [CourseStaffRole.ROLE, CourseInstructorRole.ROLE, CourseLimitedStaffRole.ROLE],
    },
    'course_weekly_report': {
        'notification_app': 'learner_progress',
        'name': 'course_weekly_report',
        'is_core': False,
        'info': '',
        'web': False,  # Robbo: off by default (the ROBBO default preset, 2026-10-23)
        'email': False,
        'push': False,
        'email_cadence': EmailCadence.DAILY,
        'non_editable': [],
        'content_template': _('<{p}>Week in <{strong}>{course_name}</{strong}>: {tests_done} tests completed, {ora_submitted} answers submitted, {waiting_review} waiting for review</{p}>'),
        'content_context': {
            'course_name': 'course_name',
            'tests_done': 'tests_done',
            'ora_submitted': 'ora_submitted',
            'waiting_review': 'waiting_review',
        },
        'email_template': '',
        'filters': [],
        'visible_to': [CourseStaffRole.ROLE, CourseInstructorRole.ROLE, CourseLimitedStaffRole.ROLE],
    },
    'course_published_by_coauthor': {
        'notification_app': 'authoring',
        'name': 'course_published_by_coauthor',
        'is_core': False,
        'info': '',
        'web': True,
        'email': False,
        'push': False,
        'email_cadence': EmailCadence.DAILY,
        'non_editable': [],
        'content_template': _('<{p}><{strong}>{author_name}</{strong}> published changes in <{strong}>{course_name}</{strong}></{p}>'),
        'content_context': {
            'author_name': 'author_name',
            'course_name': 'course_name',
        },
        'email_template': '',
        'filters': [],
        'visible_to': [CourseStaffRole.ROLE, CourseInstructorRole.ROLE, CourseLimitedStaffRole.ROLE],
    },
    'course_import_export': {
        'notification_app': 'authoring',
        'name': 'course_import_export',
        'is_core': False,
        'info': '',
        'web': False,  # Robbo: off by default (the ROBBO default preset, 2026-10-23)
        'email': False,
        'push': False,
        'email_cadence': EmailCadence.DAILY,
        'non_editable': [],
        'content_template': _('<{p}>Course {operation} {result}: <{strong}>{course_name}</{strong}></{p}>'),
        'content_context': {
            'operation': 'operation',
            'result': 'result',
            'course_name': 'course_name',
        },
        'email_template': '',
        'filters': [],
        'visible_to': [CourseStaffRole.ROLE, CourseInstructorRole.ROLE, CourseLimitedStaffRole.ROLE],
    },
    'added_to_course_team': {
        'notification_app': 'authoring',
        'name': 'added_to_course_team',
        'is_core': False,
        'info': '',
        'web': True,
        'email': False,
        'push': False,
        'email_cadence': EmailCadence.DAILY,
        'non_editable': [],
        'content_template': _('<{p}>You were added to the team of <{strong}>{course_name}</{strong}></{p}>'),
        'content_context': {
            'course_name': 'course_name',
        },
        'email_template': '',
        'filters': [],
        'visible_to': [CourseStaffRole.ROLE, CourseInstructorRole.ROLE, CourseLimitedStaffRole.ROLE],
    },
}

COURSE_NOTIFICATION_APPS = {
    'discussion': {
        'enabled': True,
        'core_info': _('Notifications for responses and comments on your posts, and the ones you’re '
                       'following, including endorsements to your responses and on your posts.'),
        'core_web': True,
        'core_email': False,  # Robbo: off by default (the ROBBO default preset, 2026-10-23)
        'core_push': True,
        'core_email_cadence': EmailCadence.DAILY,
        'non_editable': []
    },
    'updates': {
        'enabled': True,
        'core_info': _('Notifications for new announcements and updates from the course team.'),
        'core_web': True,
        'core_email': True,
        'core_push': True,
        'core_email_cadence': EmailCadence.DAILY,
        'non_editable': []
    },
    'grading': {
        'enabled': True,
        'core_info': _('Notifications for submission grading.'),
        'core_web': True,
        'core_email': True,
        'core_push': True,
        'core_email_cadence': EmailCadence.DAILY,
        'non_editable': []
    },
    # Robbo: learners' own course events (deadlines, sections, certificates, grades, enrollment).
    'learning': {
        'enabled': True,
        'core_info': '',
        'core_web': False,
        'core_email': False,
        'core_push': False,
        'core_email_cadence': EmailCadence.DAILY,
        'non_editable': []
    },
    # Robbo: course authoring in Studio (co-authors' publishing, import/export, joining a team).
    'authoring': {
        'enabled': True,
        'core_info': '',
        'core_web': False,
        'core_email': False,
        'core_push': False,
        'core_email_cadence': EmailCadence.DAILY,
        'non_editable': []
    },
    # Robbo: learner progress for the course team (learner_* types above).
    'learner_progress': {
        'enabled': True,
        'core_info': '',
        'core_web': False,
        'core_email': False,
        'core_push': False,
        'core_email_cadence': EmailCadence.DAILY,
        'non_editable': []
    },
}


class NotificationPreferenceSyncManager:
    """
    Sync Manager for Notification Preferences
    """

    @staticmethod
    def normalize_preferences(preferences):
        """
        Normalizes preferences to reduce depth of structure.
        This simplifies matching of preferences reducing effort to get difference.
        """
        apps = []
        prefs = []
        non_editable = {}
        core_notifications = {}

        for app, app_pref in preferences.items():
            apps.append({
                'name': app,
                'enabled': app_pref.get('enabled')
            })
            for pref_name, pref_values in app_pref.get('notification_types', {}).items():
                prefs.append({
                    'name': pref_name,
                    'app_name': app,
                    **pref_values
                })
            non_editable[app] = app_pref.get('non_editable', {})
            core_notifications[app] = app_pref.get('core_notification_types', [])

        normalized_preferences = {
            'apps': apps,
            'preferences': prefs,
            'non_editable': non_editable,
            'core_notifications': core_notifications,
        }
        return normalized_preferences

    @staticmethod
    def denormalize_preferences(normalized_preferences):
        """
        Denormalizes preference from simplified to normal structure for saving it in database
        """
        denormalized_preferences = {}
        for app in normalized_preferences.get('apps', []):
            app_name = app.get('name')
            app_toggle = app.get('enabled')
            denormalized_preferences[app_name] = {
                'enabled': app_toggle,
                'core_notification_types': normalized_preferences.get('core_notifications', {}).get(app_name, []),
                'notification_types': {},
                'non_editable': normalized_preferences.get('non_editable', {}).get(app_name, {}),
            }

        for preference in normalized_preferences.get('preferences', []):
            pref_name = preference.get('name')
            app_name = preference.get('app_name')
            denormalized_preferences[app_name]['notification_types'][pref_name] = {
                'web': preference.get('web'),
                'push': preference.get('push'),
                'email': preference.get('email'),
                'email_cadence': preference.get('email_cadence'),
            }
        return denormalized_preferences

    @staticmethod
    def update_preferences(preferences, email_opt_out=False):
        """
        Creates a new preference version from old preferences.
        New preference is created instead of updating old preference

        Steps to update existing user preference
            1) Normalize existing user preference
            2) Normalize default preferences
            3) Iterate over all the apps in default preference, if app_name exists in
               existing preference, update new preference app enabled value as
               existing enabled value
            4) Iterate over all preferences, if preference_name exists in existing
               preference, update new preference values of web, email and push as
               existing web, email and push respectively
            5) Denormalize new preference
        """
        old_preferences = NotificationPreferenceSyncManager.normalize_preferences(preferences)
        default_prefs = NotificationAppManager().get_notification_app_preferences(email_opt_out)
        new_prefs = NotificationPreferenceSyncManager.normalize_preferences(default_prefs)

        for app in new_prefs.get('apps'):
            app_pref = find_app_in_normalized_apps(app.get('name'), old_preferences.get('apps'))
            if app_pref:
                app['enabled'] = app_pref['enabled']

        for preference in new_prefs.get('preferences'):
            pref_name = preference.get('name')
            app_name = preference.get('app_name')
            pref = find_pref_in_normalized_prefs(pref_name, app_name, old_preferences.get('preferences'))
            if pref:
                for channel in ['web', 'email', 'push', 'email_cadence']:
                    preference[channel] = pref.get(channel, preference.get(channel))
        return NotificationPreferenceSyncManager.denormalize_preferences(new_prefs)


class NotificationTypeManager:
    """
    Manager for notification types
    """

    def __init__(self):
        self.notification_types = COURSE_NOTIFICATION_TYPES

    def get_notification_types_by_app(self, notification_app):
        """
        Returns notification types for the given notification app.
        """
        return [
            notification_type.copy() for _, notification_type in self.notification_types.items()
            if notification_type.get('notification_app', None) == notification_app
        ]

    def get_core_and_non_core_notification_types(self, notification_app):
        """
        Returns core notification types for the given app name.
        """
        notification_types = self.get_notification_types_by_app(notification_app)
        core_notification_types = []
        non_core_notification_types = []
        for notification_type in notification_types:
            if notification_type.get('is_core', None):
                core_notification_types.append(notification_type)
            else:
                non_core_notification_types.append(notification_type)
        return core_notification_types, non_core_notification_types

    @staticmethod
    def get_non_editable_notification_channels(notification_types):
        """
        Returns non_editable notification channels for the given notification types.
        """
        non_editable_notification_channels = {}
        for notification_type in notification_types:
            if notification_type.get('non_editable', None):
                non_editable_notification_channels[notification_type.get('name')] = \
                    notification_type.get('non_editable')
        return non_editable_notification_channels

    @staticmethod
    def get_non_core_notification_type_preferences(non_core_notification_types, email_opt_out=False):
        """
        Returns non-core notification type preferences for the given notification types.
        """
        non_core_notification_type_preferences = {}
        for notification_type in non_core_notification_types:
            non_core_notification_type_preferences[notification_type.get('name')] = {
                'web': notification_type.get('web', False),
                'email': False if email_opt_out else notification_type.get('email', False),
                'push': notification_type.get('push', False),
                'email_cadence': notification_type.get('email_cadence', 'Daily'),
            }
        return non_core_notification_type_preferences

    def get_notification_app_preference(self, notification_app, email_opt_out=False):
        """
        Returns notification app preferences for the given notification app.
        """
        core_notification_types, non_core_notification_types = self.get_core_and_non_core_notification_types(
            notification_app,
        )
        non_core_notification_types_preferences = self.get_non_core_notification_type_preferences(
            non_core_notification_types, email_opt_out
        )
        non_editable_notification_channels = self.get_non_editable_notification_channels(non_core_notification_types)
        core_notification_types_name = [notification_type.get('name') for notification_type in core_notification_types]
        return non_core_notification_types_preferences, core_notification_types_name, non_editable_notification_channels


class NotificationAppManager:
    """
    Notification app manager
    """

    def add_core_notification_preference(self, notification_app_attrs, notification_types, email_opt_out=False):
        """
        Adds core notification preference for the given notification app.
        """
        notification_types['core'] = {
            'web': notification_app_attrs.get('core_web', False),
            'email': False if email_opt_out else notification_app_attrs.get('core_email', False),
            'push': notification_app_attrs.get('core_push', False),
            'email_cadence': notification_app_attrs.get('core_email_cadence', 'Daily'),
        }

    def add_core_notification_non_editable(self, notification_app_attrs, non_editable_channels):
        """
        Adds non_editable for core notification.
        """
        if notification_app_attrs.get('non_editable', None):
            non_editable_channels['core'] = notification_app_attrs.get('non_editable')

    def get_notification_app_preferences(self, email_opt_out=False):
        """
        Returns notification app preferences for the given name.
        """
        course_notification_preference_config = {}
        for notification_app_key, notification_app_attrs in COURSE_NOTIFICATION_APPS.items():
            notification_app_preferences = {}
            notification_types, core_notifications, \
                non_editable_channels = NotificationTypeManager().get_notification_app_preference(
                    notification_app_key,
                    email_opt_out
                )
            self.add_core_notification_preference(notification_app_attrs, notification_types, email_opt_out)
            self.add_core_notification_non_editable(notification_app_attrs, non_editable_channels)

            notification_app_preferences['enabled'] = notification_app_attrs.get('enabled', False)
            notification_app_preferences['core_notification_types'] = core_notifications
            notification_app_preferences['notification_types'] = notification_types
            notification_app_preferences['non_editable'] = non_editable_channels
            course_notification_preference_config[notification_app_key] = notification_app_preferences
        return course_notification_preference_config


def get_notification_content(notification_type, context):
    """
    Returns notification content for the given notification type with provided context.

    Args:
    notification_type (str): The type of notification (e.g., 'course_update').
    context (dict): The context data to be used in the notification template.

    Returns:
    str: Rendered notification content based on the template and context.
    """
    context.update({
        'strong': 'strong',
        'p': 'p',
    })

    # Retrieve the function associated with the notification type.
    context_function = get_notification_type_context_function(notification_type)

    # Fix a specific case where 'course_update' needs to be renamed to 'course_updates'.
    if notification_type == 'course_update':
        notification_type = 'course_updates'

    # Retrieve the notification type object from NotificationTypeManager.
    notification_type = NotificationTypeManager().notification_types.get(notification_type, None)

    if notification_type:
        # Check if the notification is grouped.
        is_grouped = context.get('grouped', False)

        # Determine the correct template key based on whether it's grouped or not.
        template_key = "grouped_content_template" if is_grouped else "content_template"

        # Get the corresponding template from the notification type.
        template = notification_type.get(template_key, None)

        # Apply the context function to transform or modify the context.
        context = context_function(context)

        if template:
            # Handle grouped templates differently by modifying the context using a different function.
            return template.format(**context)

    return ''


def get_default_values_of_preference(notification_app, notification_type):
    """
    Returns default preference for notification_type
    """
    default_prefs = NotificationAppManager().get_notification_app_preferences()
    app_prefs = default_prefs.get(notification_app, {})
    core_notification_types = app_prefs.get('core_notification_types', [])
    notification_types = app_prefs.get('notification_types', {})
    if notification_type in core_notification_types:
        return notification_types.get('core', {})
    return notification_types.get(notification_type, {})
