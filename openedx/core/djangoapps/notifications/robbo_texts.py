"""
Robbo: notification texts for emails, in the recipient's language.

The stock ``content_template`` strings are English only and put learner input (post titles,
names) into HTML unescaped. Emails (immediate and digests) use these texts instead: values are
escaped, only <strong> comes from here. The same texts live in the Account MFE feed
(``notifications-feed/messages.js``) and the header panel (``robbo_notifications/widget``).

Copyright (C) 2026 Robbo <https://robbo.ru>
SPDX-License-Identifier: AGPL-3.0-only
Part of the Robbo Open edX distribution. See NOTICE at repository root.
"""
import html
import re

from django.utils.html import escape, format_html, strip_tags

# {name} is a plain value, [name] the same value in bold.
TEXTS = {
    'ru': {
        'course_updates': '{course_update_content}',
        'ora_staff_notifications': 'Новый ответ ждёт проверки: [ora_name]',
        'ora_staff_notifications+grouped': 'Несколько ответов ждут проверки: [ora_name]',
        'ora_grade_assigned': 'Ваш ответ на задание [ora_name] проверен: {points_earned} из {points_possible_points}',
        'new_discussion_post': 'Новая тема от [username]: [post_title]',
        'new_discussion_post+grouped': '[replier_name] и другие участники начали новые обсуждения',
        'new_question_post': 'Новый вопрос от [username]: [post_title]',
        'new_response': 'Новый ответ от [replier_name] в вашей теме [post_title]',
        'new_comment': 'Новый комментарий от [replier_name] к ответу [author_name] в вашей теме [post_title]',
        'new_comment_on_response': 'Новый комментарий от [replier_name] к вашему ответу в теме [post_title]',
        'response_on_followed_post': 'Новый ответ от [replier_name] в теме, на которую вы подписаны: [post_title]',
        'comment_on_followed_post': (
            'Новый комментарий от [replier_name] к ответу [author_name] в теме, на которую вы подписаны: [post_title]'
        ),
        'content_reported': 'Жалоба на {content_type_ru} пользователя [username]: [content]',
        'response_endorsed_on_thread': 'Ответ [replier_name] отмечен как верный в вашей теме [post_title]',
        'response_endorsed': 'Ваш ответ отмечен как верный в теме [post_title]',
        'learner_test_completed': '[learner_name] — пройден тест [test_name]: {points_earned} из {points_possible_points}',
        'learner_all_tests_completed': '[learner_name] — пройдены все тесты курса ({count})',
        'learner_ora_submitted': '[learner_name] — сдано задание [ora_name]',
        'learner_all_ora_submitted': '[learner_name] — сданы все задания с развёрнутым ответом ({count})',
        'learner_course_completed': '[learner_name] — пройдены все тесты и задания курса',
        'learner_deadline_soon': 'Скоро срок сдачи: [block_name] — до {due_ru}',
        'learner_section_released': 'Открылся новый раздел: [section_name]',
        'learner_certificate_issued': 'Сертификат по курсу [course_name] готов',
        'learner_certificate_offer': 'Курс [course_name] пройден — сертификат можно оформить за {price_display}',
        'learner_grade_changed': 'Преподаватель изменил оценку за [item_name]: {points_earned} из {points_possible_points}',
        'learner_added_to_course': 'Вас записали на курс [course_name]',
        'learner_enrolled': 'Новый ученик в курсе: [learner_name]',
        'learner_unenrolled': 'Ученик покинул курс: [learner_name]',
        'learner_low_score': '[learner_name] — низкий балл за тест [test_name]: {points_earned} из {points_possible_points}',
        'learner_missed_deadline': '[learner_name] — срок сдачи [block_name] прошёл, работа не сдана',
        'learner_inactive': '[learner_name] — нет активности в курсе {days_ru}',
        'submission_review_overdue': 'Ответ [learner_name] на задание [ora_name] ждёт проверки {days_ru}',
        'course_weekly_report': 'Неделя в курсе [course_name]: пройдено тестов — {tests_done}, сдано заданий — {ora_submitted}, ждут проверки — {waiting_review}, не заходили больше двух недель — {inactive}',
        'course_published_by_coauthor': 'Новые изменения в курсе [course_name] от [author_name]',
        'course_import_export': '{operation_ru} курса [course_name] {result_ru}',
        'added_to_course_team': 'Вас добавили в команду курса [course_name]',
    },
    'en': {
        'course_updates': '{course_update_content}',
        'ora_staff_notifications': 'A new submission is waiting for review: [ora_name]',
        'ora_staff_notifications+grouped': 'Several submissions are waiting for review: [ora_name]',
        'ora_grade_assigned': 'Your answer to [ora_name] has been graded: {points_earned} out of {points_possible}',
        'new_discussion_post': 'New post by [username]: [post_title]',
        'new_discussion_post+grouped': '[replier_name] and others started new discussions',
        'new_question_post': 'New question by [username]: [post_title]',
        'new_response': 'New reply by [replier_name] to your post [post_title]',
        'new_comment': 'New comment by [replier_name] on the reply by [author_name] to your post [post_title]',
        'new_comment_on_response': 'New comment by [replier_name] on your reply in [post_title]',
        'response_on_followed_post': 'New reply by [replier_name] in a post you follow: [post_title]',
        'comment_on_followed_post': (
            'New comment by [replier_name] on the reply by [author_name] in a post you follow: [post_title]'
        ),
        'content_reported': '{content_type_en} by [username] was reported: [content]',
        'response_endorsed_on_thread': 'The reply by [replier_name] was marked as the answer in your post [post_title]',
        'response_endorsed': 'Your reply was marked as the answer in [post_title]',
        'learner_test_completed': '[learner_name] completed the test [test_name]: {points_earned} of {points_possible}',
        'learner_all_tests_completed': '[learner_name] completed all tests of the course ({count})',
        'learner_ora_submitted': '[learner_name] submitted [ora_name]',
        'learner_all_ora_submitted': '[learner_name] submitted all open response assignments ({count})',
        'learner_course_completed': '[learner_name] completed all tests and assignments of the course',
        'learner_deadline_soon': 'Deadline soon: [block_name] — by {due_en}',
        'learner_section_released': 'A new section is open: [section_name]',
        'learner_certificate_issued': 'Your certificate for [course_name] is ready',
        'learner_certificate_offer': 'You passed [course_name]: the certificate is available for {price_display}',
        'learner_grade_changed': 'Your grade for [item_name] was changed: {points_earned} of {points_possible}',
        'learner_added_to_course': 'You were enrolled in [course_name]',
        'learner_enrolled': '[learner_name] enrolled in the course',
        'learner_unenrolled': '[learner_name] left the course',
        'learner_low_score': '[learner_name] — low score on [test_name]: {points_earned} of {points_possible}',
        'learner_missed_deadline': '[learner_name] missed the deadline for [block_name]',
        'learner_inactive': '[learner_name] has not been active for {days} days',
        'submission_review_overdue': 'The answer of [learner_name] to [ora_name] has been waiting for review for {days} days',
        'course_weekly_report': 'Week in [course_name]: {tests_done} tests completed, {ora_submitted} answers submitted, {waiting_review} waiting for review, {inactive} inactive for two weeks',
        'course_published_by_coauthor': '[author_name] published changes in [course_name]',
        'course_import_export': 'Course {operation} {result_en}: [course_name]',
        'added_to_course_team': 'You were added to the team of [course_name]',
    },
}

TYPE_LABELS = {
    'ru': {
        'course_updates': 'Обновление курса',
        'ora_staff_notifications': 'Задание на проверку',
        'ora_grade_assigned': 'Задание проверено',
        'content_reported': 'Жалоба',
        'learner_test_completed': 'Прогресс ученика',
        'learner_all_tests_completed': 'Прогресс ученика',
        'learner_ora_submitted': 'Прогресс ученика',
        'learner_all_ora_submitted': 'Прогресс ученика',
        'learner_course_completed': 'Прогресс ученика',
        'learner_deadline_soon': 'Скоро срок',
        'learner_section_released': 'Новый раздел',
        'learner_certificate_issued': 'Сертификат',
        'learner_certificate_offer': 'Сертификат',
        'learner_grade_changed': 'Оценка изменена',
        'learner_added_to_course': 'Запись на курс',
        'learner_enrolled': 'Новый ученик',
        'learner_unenrolled': 'Ученик ушёл',
        'learner_low_score': 'Низкий балл',
        'learner_missed_deadline': 'Срок пропущен',
        'learner_inactive': 'Нет активности',
        'submission_review_overdue': 'Ждёт проверки',
        'course_weekly_report': 'Отчёт за неделю',
        'course_published_by_coauthor': 'Студия',
        'course_import_export': 'Студия',
        'added_to_course_team': 'Команда курса',
        '': 'Обсуждение',
    },
    'en': {
        'course_updates': 'Course update',
        'ora_staff_notifications': 'Assignment to grade',
        'ora_grade_assigned': 'Assignment graded',
        'content_reported': 'Report',
        'learner_test_completed': 'Learner progress',
        'learner_all_tests_completed': 'Learner progress',
        'learner_ora_submitted': 'Learner progress',
        'learner_all_ora_submitted': 'Learner progress',
        'learner_course_completed': 'Learner progress',
        'learner_deadline_soon': 'Deadline soon',
        'learner_section_released': 'New section',
        'learner_certificate_issued': 'Certificate',
        'learner_certificate_offer': 'Certificate',
        'learner_grade_changed': 'Grade changed',
        'learner_added_to_course': 'Enrollment',
        'learner_enrolled': 'New learner',
        'learner_unenrolled': 'A learner left',
        'learner_low_score': 'Low score',
        'learner_missed_deadline': 'Missed deadline',
        'learner_inactive': 'No activity',
        'submission_review_overdue': 'Waiting for review',
        'course_weekly_report': 'Weekly report',
        'course_published_by_coauthor': 'Studio',
        'course_import_export': 'Studio',
        'added_to_course_team': 'Course team',
        '': 'Discussion',
    },
}

CONTENT_TYPES_RU = {'thread': 'тему', 'response': 'ответ', 'comment': 'комментарий'}
CONTENT_TYPES_EN = {'thread': 'Post', 'response': 'Reply', 'comment': 'Comment'}

# Upstream default of NOTIFICATIONS_DEFAULT_FROM_EMAIL (lms/envs/common.py); Tutor cannot set it.
_UPSTREAM_NOTIFICATIONS_FROM = 'no-reply@example.com'


def notification_from_email():
    """Sender of notification emails (immediate and digests): NOTIFICATIONS_DEFAULT_FROM_EMAIL when it is
    really set, else the site sender DEFAULT_FROM_EMAIL (Tutor CONTACT_EMAIL). A mail server that allows
    sending only as the account it logs in with then needs one setting."""
    from django.conf import settings  # pylint: disable=import-outside-toplevel
    configured = getattr(settings, 'NOTIFICATIONS_DEFAULT_FROM_EMAIL', '')
    if configured and configured != _UPSTREAM_NOTIFICATIONS_FROM:
        return configured
    return settings.DEFAULT_FROM_EMAIL


TOKEN = re.compile(r'\{(\w+)\}|\[(\w+)\]')


def lang_of(language):
    return 'ru' if (language or '').lower().startswith('ru') else 'en'


def ru_points(number):
    """«1 балла», «5 баллов» — genitive after «из»."""
    try:
        n = abs(int(number))
    except (TypeError, ValueError):
        return f'{number} балла'
    if n % 10 == 1 and n % 100 != 11:
        return f'{number} балла'
    return f'{number} баллов'


MONTHS_RU = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября',
             'ноября', 'декабря']
MONTHS_EN = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October',
             'November', 'December']


def ru_days(number):
    """«1 день», «3 дня», «14 дней»."""
    try:
        n = abs(int(number))
    except (TypeError, ValueError):
        return str(number)
    if n % 10 == 1 and n % 100 != 11:
        return f'{n} день'
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return f'{n} дня'
    return f'{n} дней'


def format_moment(iso, lang, zone_name=None):
    """An ISO moment as «25 октября, 23:59» (Moscow for ru, UTC for en unless a zone is given)."""
    from datetime import datetime  # pylint: disable=import-outside-toplevel
    import pytz  # pylint: disable=import-outside-toplevel
    try:
        moment = datetime.fromisoformat(str(iso))
    except ValueError:
        return str(iso)
    if moment.tzinfo is None:
        moment = pytz.UTC.localize(moment)
    zone = pytz.timezone(zone_name or ('Europe/Moscow' if lang == 'ru' else 'UTC'))
    moment = moment.astimezone(zone)
    if lang == 'ru':
        return f'{moment.day} {MONTHS_RU[moment.month - 1]}, {moment:%H:%M}'
    return f'{MONTHS_EN[moment.month - 1]} {moment.day}, {moment:%H:%M}'


def _values(context):
    values = {key: '' if value is None else str(value) for key, value in (context or {}).items()}
    values['course_update_content'] = re.sub(r'\s+', ' ', strip_tags(values.get('course_update_content', ''))).strip()
    values['content'] = strip_tags(values.get('content', '')).strip()
    values['points_possible_points'] = ru_points(values.get('points_possible', ''))
    values['days_ru'] = ru_days(values.get('days', ''))
    values['due_ru'] = format_moment(values.get('due', ''), 'ru')
    values['due_en'] = format_moment(values.get('due', ''), 'en')
    operation = values.get('operation', '')
    values['operation_ru'] = {'import': 'Импорт', 'export': 'Экспорт'}.get(operation, operation)
    succeeded = values.get('result', '') == 'succeeded'
    values['result_ru'] = 'завершён' if succeeded else 'не удался'
    values['result_en'] = 'finished' if succeeded else 'failed'
    content_type = values.get('content_type', '')
    values['content_type_ru'] = CONTENT_TYPES_RU.get(content_type, 'сообщение')
    values['content_type_en'] = CONTENT_TYPES_EN.get(content_type, 'Message')
    return values


def notification_html(notification_type, context, language):
    """Safe HTML of one notification, or '' for a type without a Robbo text."""
    lang = lang_of(language)
    key = f'{notification_type}+grouped' if (context or {}).get('grouped') else notification_type
    template = TEXTS[lang].get(key) or TEXTS[lang].get(notification_type)
    if not template:
        return ''
    values = _values(context)

    def render(match):
        plain, bold = match.groups()
        if plain:
            return escape(values.get(plain, ''))
        return str(format_html('<strong>{}</strong>', values.get(bold, '')))

    return TOKEN.sub(render, template)


def notification_text(notification_type, context, language):
    """Plain text of one notification (email subject, text part)."""
    return html.unescape(strip_tags(notification_html(notification_type, context, language)))


def type_label(notification_type, language):
    labels = TYPE_LABELS[lang_of(language)]
    return labels.get(notification_type, labels[''])
