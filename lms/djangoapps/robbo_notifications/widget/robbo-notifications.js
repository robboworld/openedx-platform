/**
 * Copyright (C) 2026 Robbo <https://robbo.ru>
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Part of the Robbo Open edX distribution. See NOTICE at repository root.
 *
 * Notifications header button: bell, unseen counter, panel with the latest notifications.
 * One implementation for every header, built like «Что нового» (robbo_changelog/widget/robbo-whats-new.js):
 * the LMS serves this file at /api/robbo/v1/notifications/widget.js to LMS pages and all MFEs.
 * Data: the stock notifications API on the LMS session (/api/notifications/…). The button stays hidden
 * for guests, accounts not activated yet and while show_notifications_tray is false.
 *
 *   RobboNotifications.mount(container, {lmsUrl, lang, variant, feedUrl})
 *       lmsUrl — host of the API (default: this page's origin); feedUrl — the full list
 *       (Account MFE /account/notifications).
 *   <span data-robbo-notifications data-lms-url data-lang data-variant data-feed-url> mounts itself.
 *
 * Opening the panel marks notifications "seen" (resets the counter); following one marks it "read", and so do
 * the tick on an unread entry and «Прочитать все» (POST /api/robbo/v1/notifications/read-all/) — without leaving
 * the page. Studio's Mako pages mount it on Studio's copy of the API (robbo_notifications/studio_urls.py).
 * Texts are built from content_context with our own messages: the LMS HTML is English and carries
 * learner input (post titles, names) without escaping, so it is never inserted as markup.
 *
 * window event "robbo:notifications-changed" (the feed page fires it) refreshes the counter; the widget fires
 * "robbo:notifications-read" ({detail: {ids} or {all: true}}) so the feed page marks the same entries read.
 */
(function () {
  'use strict';

  if (window.RobboNotifications) {
    return;
  }

  var API = '/api/notifications/';
  var READ_ALL_PATH = '/api/robbo/v1/notifications/read-all/';
  var READ_EVENT = 'robbo:notifications-read';
  var PAGE_SIZE = 10;
  var STYLE_ID = 'robbo-nt-style';
  var CHANGED_EVENT = 'robbo:notifications-changed';
  var NARROW_QUERY = '(max-width: 575.98px)';
  var REDUCED_MOTION_QUERY = '(prefers-reduced-motion: reduce)';
  var CLOSE_DELAY = 160;
  var counter = 0;

  function svg(paths, size) {
    return '<svg viewBox="0 0 24 24" width="' + size + '" height="' + size + '" aria-hidden="true" focusable="false" '
      + 'fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
      + paths + '</svg>';
  }

  var ICON_BELL = svg('<path d="M6 10a6 6 0 0112 0c0 4.2 1.6 5.9 2.2 6.5a.5.5 0 01-.4.9H4.2a.5.5 0 01-.4-.9'
    + 'C4.4 15.9 6 14.2 6 10z"/><path d="M10 20.2a2.3 2.3 0 004 0"/>', 20);
  var ICON_CLOSE = svg('<path d="M6 6l12 12M18 6L6 18"/>', 18);
  var ICON_ARROW = svg('<path d="M5 12h14M13 6l6 6-6 6"/>', 16);
  var ICON_CHECK = svg('<path d="M5 12.5l4.5 4.5L19 7.5"/>', 16);
  var ICON_CHECK_ALL = svg('<path d="M2 12.5l4.5 4.5L16 7.5"/><path d="M11.5 16l1 1L22 7.5"/>', 16);
  var ICON_EMPTY = svg('<path d="M6 10a6 6 0 0112 0c0 4.2 1.6 5.9 2.2 6.5a.5.5 0 01-.4.9H4.2a.5.5 0 01-.4-.9'
    + 'C4.4 15.9 6 14.2 6 10z"/><path d="M10 20.2a2.3 2.3 0 004 0"/>', 28);
  var TYPE_ICONS = {
    course_updates: svg('<path d="M4 10v4a1 1 0 001 1h2l5 4V5L7 9H5a1 1 0 00-1 1z"/>'
      + '<path d="M16 9a4 4 0 010 6"/><path d="M18.5 6.5a7.5 7.5 0 010 11"/>', 16),
    ora_staff_notifications: svg('<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4V3h6v1"/>'
      + '<path d="M9 10h6M9 14h6M9 18h3"/>', 16),
    ora_grade_assigned: svg('<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 12.5l2 2 4-4.5"/>', 16),
    content_reported: svg('<path d="M5 21V4"/><path d="M5 4h11l-2 4 2 4H5"/>', 16),
    // Robbo learner progress (course team): learner_* types.
    learner_progress: svg('<circle cx="9" cy="8" r="3.5"/><path d="M3 20a6 6 0 0112 0"/>'
      + '<path d="M15.5 12.5l2 2 4-4.5"/>', 16),
    // Robbo: more notifications (learning, team, Studio).
    learner_deadline_soon: svg('<rect x="4" y="5" width="16" height="15" rx="2"/><path d="M8 3v4M16 3v4M4 10h16"/>'
      + '<path d="M12 13v3l2 1"/>', 16),
    learner_section_released: svg('<path d="M4 5h6a2 2 0 012 2v12a2 2 0 00-2-2H4z"/><path d="M20 5h-6a2 2 0 00-2 2v12a2 2 0 012-2h6z"/>', 16),
    learner_certificate_issued: svg('<circle cx="12" cy="9" r="5"/><path d="M9 13.5L8 21l4-2 4 2-1-7.5"/>', 16),
    learner_certificate_offer: svg('<circle cx="12" cy="9" r="5"/><path d="M9 13.5L8 21l4-2 4 2-1-7.5"/>', 16),
    learner_grade_changed: svg('<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 12.5l2 2 4-4.5"/>', 16),
    learner_added_to_course: svg('<path d="M3 9l9-5 9 5-9 5z"/><path d="M7 11v5c0 1.5 2.2 3 5 3s5-1.5 5-3v-5"/>', 16),
    learner_enrolled: svg('<circle cx="10" cy="8" r="3.5"/><path d="M4 20a6 6 0 0112 0"/><path d="M19 8v6M16 11h6"/>', 16),
    learner_unenrolled: svg('<circle cx="10" cy="8" r="3.5"/><path d="M4 20a6 6 0 0112 0"/><path d="M16 11h6"/>', 16),
    learner_low_score: svg('<path d="M4 7l6 6 4-4 6 6"/><path d="M20 10v5h-5"/>', 16),
    learner_missed_deadline: svg('<rect x="4" y="5" width="16" height="15" rx="2"/><path d="M8 3v4M16 3v4M4 10h16"/>'
      + '<path d="M10 13l4 4M14 13l-4 4"/>', 16),
    learner_inactive: svg('<circle cx="10" cy="8" r="3.5"/><path d="M4 20a6 6 0 0112 0"/><path d="M17 4l4 4M21 4l-4 4"/>', 16),
    submission_review_overdue: svg('<path d="M7 3h10M7 21h10"/><path d="M8 3c0 5 8 5 8 9s-8 4-8 9"/><path d="M16 3c0 5-8 5-8 9"/>', 16),
    course_weekly_report: svg('<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>', 16),
    course_published_by_coauthor: svg('<path d="M12 16V4M7 9l5-5 5 5"/><path d="M5 20h14"/>', 16),
    course_import_export: svg('<path d="M7 4v13M3 13l4 4 4-4"/><path d="M17 20V7M13 11l4-4 4 4"/>', 16),
    added_to_course_team: svg('<circle cx="9" cy="8" r="3"/><circle cx="17" cy="9" r="2.5"/><path d="M3 20a6 6 0 0112 0"/>'
      + '<path d="M15 15a5 5 0 016 5"/>', 16),
    discussion: svg('<path d="M4 5h12a1 1 0 011 1v7a1 1 0 01-1 1H9l-4 3v-3H4a1 1 0 01-1-1V6a1 1 0 011-1z"/>'
      + '<path d="M17 9h3a1 1 0 011 1v7a1 1 0 01-1 1h-1v3l-4-3h-4a1 1 0 01-1-1v-1"/>', 16),
  };

  var PLURAL_RU = function (n, forms) {
    var mod10 = n % 10;
    var mod100 = n % 100;
    if (Math.floor(n) !== n) {
      return forms.other;
    }
    if (mod10 === 1 && mod100 !== 11) {
      return forms.one;
    }
    if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) {
      return forms.few;
    }
    return forms.many;
  };

  var MONTHS = {
    ru: ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября',
      'декабря'],
    en: ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November',
      'December'],
  };
  // A deadline in the reader's time zone: «25 октября, 23:59».
  var formatMoment = function (iso, lang) {
    var d = new Date(iso);
    if (isNaN(d.getTime())) {
      return String(iso || '');
    }
    var time = ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2);
    var month = MONTHS[lang][d.getMonth()];
    return lang === 'ru' ? d.getDate() + ' ' + month + ', ' + time : month + ' ' + d.getDate() + ', ' + time;
  };

  // Each message returns a list of parts: plain strings and {b: text} (bold). Never HTML.
  var TEXTS = {
    ru: {
      title: 'Уведомления',
      buttonUnread: 'Уведомления, новых: {count}',
      summaryNone: 'Новых уведомлений нет',
      summaryNew: function (n) {
        return n + ' ' + PLURAL_RU(n, {one: 'новое', few: 'новых', many: 'новых', other: 'новых'});
      },
      close: 'Закрыть',
      all: 'Все уведомления',
      unread: 'Не прочитано',
      markRead: 'Отметить прочитанным',
      readAll: 'Прочитать все',
      readAllDone: 'Все уведомления прочитаны',
      readError: 'Не удалось отметить. Попробуйте ещё раз.',
      loading: 'Загружаем уведомления',
      error: 'Не удалось загрузить уведомления. Попробуйте позже.',
      emptyTitle: 'Уведомлений пока нет',
      emptyBody: 'Здесь появятся обновления курсов, результаты проверки заданий и ответы в обсуждениях.',
      today: 'Сегодня',
      yesterday: 'Вчера',
      types: {
        course_updates: 'Обновление курса',
        ora_staff_notifications: 'Задание на проверку',
        ora_grade_assigned: 'Задание проверено',
        content_reported: 'Жалоба',
        learner_progress: 'Прогресс ученика',
        learner_deadline_soon: 'Скоро срок',
        learner_section_released: 'Новый раздел',
        learner_certificate_issued: 'Сертификат',
        learner_certificate_offer: 'Сертификат',
        learner_grade_changed: 'Оценка изменена',
        learner_added_to_course: 'Запись на курс',
        learner_enrolled: 'Новый ученик',
        learner_unenrolled: 'Ученик ушёл',
        learner_low_score: 'Низкий балл',
        learner_missed_deadline: 'Срок пропущен',
        learner_inactive: 'Нет активности',
        submission_review_overdue: 'Ждёт проверки',
        course_weekly_report: 'Отчёт за неделю',
        course_published_by_coauthor: 'Студия',
        course_import_export: 'Студия',
        added_to_course_team: 'Команда курса',
        other: 'Обсуждение',
      },
      messages: {
        ora_staff_notifications: function (c) {
          return [c.grouped ? 'Несколько ответов ждут проверки: ' : 'Новый ответ ждёт проверки: ', {b: c.ora_name}];
        },
        ora_grade_assigned: function (c) {
          var possible = Number(c.points_possible);
          return ['Ваш ответ на задание ', {b: c.ora_name}, ' проверен: ' + c.points_earned + ' из ' + c.points_possible + ' '
            + PLURAL_RU(possible, {one: 'балла', few: 'баллов', many: 'баллов', other: 'балла'})];
        },
        new_discussion_post: function (c) {
          return c.grouped
            ? [{b: c.username}, ' и другие участники начали новые обсуждения']
            : ['Новая тема от ', {b: c.username}, ': ', {b: c.post_title}];
        },
        new_question_post: function (c) { return ['Новый вопрос от ', {b: c.username}, ': ', {b: c.post_title}]; },
        new_response: function (c) {
          return ['Новый ответ от ', {b: c.replier_name}, ' в вашей теме ', {b: c.post_title}];
        },
        new_comment: function (c) {
          return ['Новый комментарий от ', {b: c.replier_name}, ' к ответу ', {b: c.author_name}, ' в вашей теме ',
            {b: c.post_title}];
        },
        new_comment_on_response: function (c) {
          return ['Новый комментарий от ', {b: c.replier_name}, ' к вашему ответу в теме ', {b: c.post_title}];
        },
        response_on_followed_post: function (c) {
          return ['Новый ответ от ', {b: c.replier_name}, ' в теме, на которую вы подписаны: ', {b: c.post_title}];
        },
        comment_on_followed_post: function (c) {
          return ['Новый комментарий от ', {b: c.replier_name}, ' к ответу ', {b: c.author_name},
            ' в теме, на которую вы подписаны: ', {b: c.post_title}];
        },
        content_reported: function (c) {
          var what = {thread: 'тему', response: 'ответ', comment: 'комментарий'}[c.content_type] || 'сообщение';
          return ['Жалоба на ' + what + ' пользователя ', {b: c.username}, ': ', {b: htmlToText(c.content)}];
        },
        response_endorsed_on_thread: function (c) {
          return ['Ответ ', {b: c.replier_name}, ' отмечен как верный в вашей теме ', {b: c.post_title}];
        },
        response_endorsed: function (c) { return ['Ваш ответ отмечен как верный в теме ', {b: c.post_title}]; },
        learner_test_completed: function (c) {
          var possible = Number(c.points_possible);
          return [{b: c.learner_name}, ' — пройден тест ', {b: c.test_name}, ': ' + c.points_earned + ' из '
            + c.points_possible + ' ' + PLURAL_RU(possible, {one: 'балла', few: 'баллов', many: 'баллов', other: 'балла'})];
        },
        learner_all_tests_completed: function (c) {
          return [{b: c.learner_name}, ' — пройдены все тесты курса (' + c.count + ')'];
        },
        learner_ora_submitted: function (c) { return [{b: c.learner_name}, ' — сдано задание ', {b: c.ora_name}]; },
        learner_all_ora_submitted: function (c) {
          return [{b: c.learner_name}, ' — сданы все задания с развёрнутым ответом (' + c.count + ')'];
        },
        learner_course_completed: function (c) {
          return [{b: c.learner_name}, ' — пройдены все тесты и задания курса'];
        },
        learner_deadline_soon: function (c) {
          return ['Скоро срок сдачи: ', {b: c.block_name}, ' — до ' + formatMoment(c.due, 'ru')];
        },
        learner_section_released: function (c) { return ['Открылся новый раздел: ', {b: c.section_name}]; },
        learner_certificate_issued: function (c) { return ['Сертификат по курсу ', {b: c.course_name}, ' готов']; },
        learner_certificate_offer: function (c) {
          return ['Курс ', {b: c.course_name}, ' пройден — сертификат можно оформить за ' + c.price_display];
        },
        learner_grade_changed: function (c) {
          var possible = Number(c.points_possible);
          return ['Преподаватель изменил оценку за ', {b: c.item_name}, ': ' + c.points_earned + ' из ' + c.points_possible + ' '
            + PLURAL_RU(possible, {one: 'балла', few: 'баллов', many: 'баллов', other: 'балла'})];
        },
        learner_added_to_course: function (c) { return ['Вас записали на курс ', {b: c.course_name}]; },
        learner_enrolled: function (c) { return ['Новый ученик в курсе: ', {b: c.learner_name}]; },
        learner_unenrolled: function (c) { return ['Ученик покинул курс: ', {b: c.learner_name}]; },
        learner_low_score: function (c) {
          var possible = Number(c.points_possible);
          return [{b: c.learner_name}, ' — низкий балл за тест ', {b: c.test_name}, ': ' + c.points_earned + ' из '
            + c.points_possible + ' ' + PLURAL_RU(possible, {one: 'балла', few: 'баллов', many: 'баллов', other: 'балла'})];
        },
        learner_missed_deadline: function (c) {
          return [{b: c.learner_name}, ' — срок сдачи ', {b: c.block_name}, ' прошёл, работа не сдана'];
        },
        learner_inactive: function (c) {
          return [{b: c.learner_name}, ' — нет активности в курсе ' + c.days + ' '
            + PLURAL_RU(Number(c.days), {one: 'день', few: 'дня', many: 'дней', other: 'дня'})];
        },
        submission_review_overdue: function (c) {
          return ['Ответ ', {b: c.learner_name}, ' на задание ', {b: c.ora_name}, ' ждёт проверки ' + c.days + ' '
            + PLURAL_RU(Number(c.days), {one: 'день', few: 'дня', many: 'дней', other: 'дня'})];
        },
        course_weekly_report: function (c) {
          return ['Неделя в курсе ', {b: c.course_name}, ': пройдено тестов — ' + c.tests_done + ', сдано заданий — '
            + c.ora_submitted + ', ждут проверки — ' + c.waiting_review + ', не заходили больше двух недель — ' + c.inactive];
        },
        course_published_by_coauthor: function (c) {
          return ['Новые изменения в курсе ', {b: c.course_name}, ' от ', {b: c.author_name}];
        },
        course_import_export: function (c) {
          return [(c.operation === 'import' ? 'Импорт' : 'Экспорт') + ' курса ', {b: c.course_name},
            c.result === 'succeeded' ? ' завершён' : ' не удался'];
        },
        added_to_course_team: function (c) { return ['Вас добавили в команду курса ', {b: c.course_name}]; },
      },
    },
    en: {
      title: 'Notifications',
      buttonUnread: 'Notifications, new: {count}',
      summaryNone: 'No new notifications',
      summaryNew: function (n) { return n + ' new'; },
      close: 'Close',
      all: 'All notifications',
      unread: 'Unread',
      markRead: 'Mark as read',
      readAll: 'Mark all as read',
      readAllDone: 'All notifications are read',
      readError: 'Could not mark as read. Please try again.',
      loading: 'Loading notifications',
      error: 'Could not load notifications. Please try again later.',
      emptyTitle: 'No notifications yet',
      emptyBody: 'Course updates, graded assignments and replies in discussions will appear here.',
      today: 'Today',
      yesterday: 'Yesterday',
      types: {
        course_updates: 'Course update',
        ora_staff_notifications: 'Assignment to grade',
        ora_grade_assigned: 'Assignment graded',
        content_reported: 'Report',
        learner_progress: 'Learner progress',
        learner_deadline_soon: 'Deadline soon',
        learner_section_released: 'New section',
        learner_certificate_issued: 'Certificate',
        learner_certificate_offer: 'Certificate',
        learner_grade_changed: 'Grade changed',
        learner_added_to_course: 'Enrollment',
        learner_enrolled: 'New learner',
        learner_unenrolled: 'A learner left',
        learner_low_score: 'Low score',
        learner_missed_deadline: 'Missed deadline',
        learner_inactive: 'No activity',
        submission_review_overdue: 'Waiting for review',
        course_weekly_report: 'Weekly report',
        course_published_by_coauthor: 'Studio',
        course_import_export: 'Studio',
        added_to_course_team: 'Course team',
        other: 'Discussion',
      },
      messages: {
        ora_staff_notifications: function (c) {
          return [c.grouped ? 'Several submissions are waiting for review: ' : 'A new submission is waiting for review: ',
            {b: c.ora_name}];
        },
        ora_grade_assigned: function (c) {
          return ['Your answer to ', {b: c.ora_name}, ' has been graded: ' + c.points_earned + ' out of '
            + c.points_possible + ' points'];
        },
        new_discussion_post: function (c) {
          return c.grouped
            ? [{b: c.username}, ' and others started new discussions']
            : ['New post by ', {b: c.username}, ': ', {b: c.post_title}];
        },
        new_question_post: function (c) { return ['New question by ', {b: c.username}, ': ', {b: c.post_title}]; },
        new_response: function (c) {
          return ['New reply by ', {b: c.replier_name}, ' to your post ', {b: c.post_title}];
        },
        new_comment: function (c) {
          return ['New comment by ', {b: c.replier_name}, ' on the reply by ', {b: c.author_name}, ' to your post ',
            {b: c.post_title}];
        },
        new_comment_on_response: function (c) {
          return ['New comment by ', {b: c.replier_name}, ' on your reply in ', {b: c.post_title}];
        },
        response_on_followed_post: function (c) {
          return ['New reply by ', {b: c.replier_name}, ' in a post you follow: ', {b: c.post_title}];
        },
        comment_on_followed_post: function (c) {
          return ['New comment by ', {b: c.replier_name}, ' on the reply by ', {b: c.author_name},
            ' in a post you follow: ', {b: c.post_title}];
        },
        content_reported: function (c) {
          var what = {thread: 'Post', response: 'Reply', comment: 'Comment'}[c.content_type] || 'Message';
          return [what + ' by ', {b: c.username}, ' was reported: ', {b: htmlToText(c.content)}];
        },
        response_endorsed_on_thread: function (c) {
          return ['The reply by ', {b: c.replier_name}, ' was marked as the answer in your post ', {b: c.post_title}];
        },
        response_endorsed: function (c) { return ['Your reply was marked as the answer in ', {b: c.post_title}]; },
        learner_test_completed: function (c) {
          return [{b: c.learner_name}, ' completed the test ', {b: c.test_name}, ': ' + c.points_earned + ' of '
            + c.points_possible];
        },
        learner_all_tests_completed: function (c) {
          return [{b: c.learner_name}, ' completed all tests of the course (' + c.count + ')'];
        },
        learner_ora_submitted: function (c) { return [{b: c.learner_name}, ' submitted ', {b: c.ora_name}]; },
        learner_all_ora_submitted: function (c) {
          return [{b: c.learner_name}, ' submitted all open response assignments (' + c.count + ')'];
        },
        learner_course_completed: function (c) {
          return [{b: c.learner_name}, ' completed all tests and assignments of the course'];
        },
        learner_deadline_soon: function (c) {
          return ['Deadline soon: ', {b: c.block_name}, ' — by ' + formatMoment(c.due, 'en')];
        },
        learner_section_released: function (c) { return ['A new section is open: ', {b: c.section_name}]; },
        learner_certificate_issued: function (c) { return ['Your certificate for ', {b: c.course_name}, ' is ready']; },
        learner_certificate_offer: function (c) {
          return ['You passed ', {b: c.course_name}, ': the certificate is available for ' + c.price_display];
        },
        learner_grade_changed: function (c) {
          return ['Your grade for ', {b: c.item_name}, ' was changed: ' + c.points_earned + ' of ' + c.points_possible];
        },
        learner_added_to_course: function (c) { return ['You were enrolled in ', {b: c.course_name}]; },
        learner_enrolled: function (c) { return ['New learner in the course: ', {b: c.learner_name}]; },
        learner_unenrolled: function (c) { return ['A learner left the course: ', {b: c.learner_name}]; },
        learner_low_score: function (c) {
          return [{b: c.learner_name}, ' — low score on ', {b: c.test_name}, ': ' + c.points_earned + ' of ' + c.points_possible];
        },
        learner_missed_deadline: function (c) {
          return [{b: c.learner_name}, ' — the deadline for ', {b: c.block_name}, ' has passed, not submitted'];
        },
        learner_inactive: function (c) {
          return [{b: c.learner_name}, ' — no activity in the course for ' + c.days + ' days'];
        },
        submission_review_overdue: function (c) {
          return ['The answer of ', {b: c.learner_name}, ' to ', {b: c.ora_name}, ' has been waiting for review for '
            + c.days + ' days'];
        },
        course_weekly_report: function (c) {
          return ['Week in ', {b: c.course_name}, ': ' + c.tests_done + ' tests completed, ' + c.ora_submitted
            + ' answers submitted, ' + c.waiting_review + ' waiting for review, ' + c.inactive + ' inactive for two weeks'];
        },
        course_published_by_coauthor: function (c) {
          return ['New changes in ', {b: c.course_name}, ' from ', {b: c.author_name}];
        },
        course_import_export: function (c) {
          return ['Course ' + (c.operation === 'import' ? 'import' : 'export')
            + (c.result === 'succeeded' ? ' finished: ' : ' failed: '), {b: c.course_name}];
        },
        added_to_course_team: function (c) { return ['You were added to the team of ', {b: c.course_name}]; },
      },
    },
  };

  // Plain CSS (no build step), the «Что нового» panel styles under robbo-nt-*: the panel lives in <body>, so every
  // rule names its own class and sets margins, fonts and colours against host styles (LMS legacy, Paragon).
  // Sizes are px, not rem. Palette — ROBBO brand: green #00af41, coal #383838, grey #989898, white.
  var CSS = [
    '.robbo-nt{--robbo-nt-green:#00af41;--robbo-nt-green-dark:#007e2f;',
    'display:inline-flex;align-items:center;flex:0 0 auto;position:relative;vertical-align:middle}',
    '.robbo-nt[hidden]{display:none}',
    '.robbo-nt.robbo-nt .robbo-nt__button{appearance:none;-webkit-appearance:none;background:transparent;',
    'background-image:none;border:1px solid currentColor;border-radius:999px;box-shadow:none;box-sizing:border-box;',
    'color:#fff;cursor:pointer;display:inline-flex;align-items:center;justify-content:center;',
    'height:calc(21.6px + 14px);width:calc(21.6px + 14px);margin:0;min-width:0;padding:0;position:relative;line-height:1;',
    'text-decoration:none;transition:background-color .15s ease,color .15s ease,transform .15s ease}',
    '.robbo-nt--on-light.robbo-nt .robbo-nt__button{color:var(--robbo-nt-green)}',
    '.robbo-nt.robbo-nt .robbo-nt__button:hover{background:rgba(255,255,255,.18)}',
    '.robbo-nt.robbo-nt .robbo-nt__button:active{transform:scale(.94)}',
    '.robbo-nt.robbo-nt .robbo-nt__button[aria-expanded="true"]{background:#fff;border-color:#fff;',
    'color:var(--robbo-nt-green-dark)}',
    '.robbo-nt--on-light.robbo-nt .robbo-nt__button:hover{background:rgba(0,175,65,.08)}',
    '.robbo-nt--on-light.robbo-nt .robbo-nt__button[aria-expanded="true"]{background:var(--robbo-nt-green);',
    'border-color:var(--robbo-nt-green);color:#fff}',
    '.robbo-nt.robbo-nt .robbo-nt__button:focus{outline:none}',
    '.robbo-nt.robbo-nt .robbo-nt__button:focus-visible{outline:2px solid #fff;outline-offset:3px}',
    '.robbo-nt--on-light.robbo-nt .robbo-nt__button:focus-visible{outline-color:var(--robbo-nt-green)}',
    '.robbo-nt .robbo-nt__button svg{display:block;pointer-events:none}',
    '.robbo-nt .robbo-nt__badge{animation:robbo-nt-pop .25s ease-out;background:#fff;border-radius:999px;',
    'box-shadow:0 0 0 2px var(--robbo-nt-green),0 1px 3px rgba(0,0,0,.25);box-sizing:border-box;',
    'color:var(--robbo-nt-green-dark);font:800 11px/18px ',
    'var(--robbo-font-body,"Proxima Nova","ProximaNova",Helvetica,Arial,sans-serif);height:18px;',
    'min-width:18px;padding:0 4px;pointer-events:none;position:absolute;right:-7px;text-align:center;top:-7px}',
    '.robbo-nt--on-light .robbo-nt__badge{background:var(--robbo-nt-green);box-shadow:0 0 0 2px #fff;color:#fff}',
    '.robbo-nt .robbo-nt__badge[hidden]{display:none}',
    '@keyframes robbo-nt-pop{from{opacity:0;transform:scale(.4)}to{opacity:1;transform:scale(1)}}',

    '.robbo-nt-panel{--robbo-nt-green:#00af41;--robbo-nt-green-dark:#007e2f;--robbo-nt-green-tint:#effaf3;',
    '--robbo-nt-green-soft:#dcf3e4;--robbo-nt-text:#1f2328;--robbo-nt-muted:#5f6670;--robbo-nt-grey:#989898;',
    '--robbo-nt-line:#e8eaed;--robbo-nt-surface:#fff;--robbo-nt-hover:#f6f7f8;--robbo-nt-chip:#f1f2f4;',
    '--robbo-nt-caret:20px;--robbo-nt-head:#e3f6ea;',
    'background:var(--robbo-nt-surface);border:1px solid var(--robbo-nt-line);border-radius:16px;',
    'box-shadow:0 18px 48px rgba(17,24,39,.18),0 2px 6px rgba(17,24,39,.08);box-sizing:border-box;',
    'color:var(--robbo-nt-text);display:flex;flex-direction:column;',
    'font-family:var(--robbo-font-body,"Proxima Nova","ProximaNova",Helvetica,Arial,sans-serif);font-size:16px;',
    'line-height:1.5;max-width:calc(100vw - 16px);opacity:0;position:fixed;text-align:left;',
    'transform:translateY(-6px) scale(.98);transform-origin:top right;',
    'transition:opacity .16s ease,transform .16s ease;width:400px;z-index:1060}',
    '.robbo-nt-panel.is-open{opacity:1;transform:none}',
    '.robbo-nt-panel[hidden]{display:none}',
    '.robbo-nt-panel *{box-sizing:border-box}',
    '.robbo-nt-panel .robbo-nt__caret{background:var(--robbo-nt-head);border-left:1px solid var(--robbo-nt-line);',
    'border-top:1px solid var(--robbo-nt-line);height:14px;left:var(--robbo-nt-caret);position:absolute;',
    'top:-7px;transform:rotate(45deg);width:14px}',
    '.robbo-nt-panel .robbo-nt__head{align-items:flex-start;display:flex;gap:12px;justify-content:space-between;',
    'background:linear-gradient(135deg,var(--robbo-nt-head) 0%,var(--robbo-nt-surface) 85%);',
    'border-radius:16px 16px 0 0;padding:16px 16px 14px 20px;position:relative}',
    '.robbo-nt-panel .robbo-nt__title{color:var(--robbo-nt-text);font-family:inherit;font-size:20px;',
    'font-style:normal;font-weight:800;letter-spacing:-.01em;line-height:1.25;margin:0;outline:none;padding:0;',
    'text-transform:none}',
    '.robbo-nt-panel .robbo-nt__summary{color:var(--robbo-nt-muted);font-size:14px;line-height:1.4;',
    'margin:2px 0 0;min-height:1.225em}',
    '.robbo-nt-panel .robbo-nt__summary.has-unread{color:var(--robbo-nt-green-dark);font-weight:700}',
    '.robbo-nt-panel.robbo-nt-panel .robbo-nt__close{align-items:center;appearance:none;-webkit-appearance:none;',
    'background:transparent;background-image:none;border:0;border-radius:999px;box-shadow:none;',
    'color:var(--robbo-nt-muted);cursor:pointer;display:inline-flex;flex:0 0 auto;height:40px;justify-content:center;',
    'margin:-4px -4px 0 0;padding:0;text-shadow:none;transition:background-color .15s ease;width:40px}',
    '.robbo-nt-panel.robbo-nt-panel .robbo-nt__close:hover{background:var(--robbo-nt-hover);color:var(--robbo-nt-text)}',
    '.robbo-nt-panel.robbo-nt-panel .robbo-nt__close:focus{outline:none}',
    '.robbo-nt-panel.robbo-nt-panel .robbo-nt__close:focus-visible{outline:2px solid var(--robbo-nt-green)}',
    '.robbo-nt-panel .robbo-nt__close svg{display:block}',
    '.robbo-nt-panel .robbo-nt__actions{align-items:center;display:flex;flex:0 0 auto;gap:2px;margin:-4px -4px 0 0}',
    '.robbo-nt-panel .robbo-nt__actions .robbo-nt__close{margin:0}',
    '.robbo-nt-panel.robbo-nt-panel .robbo-nt__read-all{align-items:center;appearance:none;-webkit-appearance:none;',
    'background:transparent;background-image:none;border:0;border-radius:999px;box-shadow:none;',
    'color:var(--robbo-nt-green-dark);cursor:pointer;display:inline-flex;font-family:inherit;font-size:13px;',
    'font-weight:700;line-height:1.2;gap:6px;height:36px;letter-spacing:0;margin:0;padding:0 12px;text-shadow:none;',
    'text-transform:none;transition:background-color .15s ease,opacity .15s ease;white-space:nowrap}',
    '.robbo-nt-panel.robbo-nt-panel .robbo-nt__read-all:hover{background:var(--robbo-nt-green-soft);',
    'color:var(--robbo-nt-green-dark)}',
    '.robbo-nt-panel.robbo-nt-panel .robbo-nt__read-all:focus{outline:none}',
    '.robbo-nt-panel.robbo-nt-panel .robbo-nt__read-all:focus-visible{outline:2px solid var(--robbo-nt-green)}',
    '.robbo-nt-panel.robbo-nt-panel .robbo-nt__read-all[disabled]{cursor:progress;opacity:.6}',
    '.robbo-nt-panel .robbo-nt__read-all[hidden]{display:none}',
    '.robbo-nt-panel .robbo-nt__read-all svg{display:block;flex:0 0 auto}',
    '.robbo-nt-panel.robbo-nt-panel .robbo-nt__mark{align-items:center;appearance:none;-webkit-appearance:none;',
    'background:transparent;background-image:none;border:1px solid transparent;border-radius:999px;box-shadow:none;',
    'color:var(--robbo-nt-green-dark);cursor:pointer;display:inline-flex;height:32px;justify-content:center;',
    'margin:0;padding:0;position:absolute;right:8px;text-shadow:none;top:10px;',
    'transition:background-color .15s ease,border-color .15s ease,opacity .15s ease;width:32px;z-index:1}',
    '.robbo-nt-panel.robbo-nt-panel .robbo-nt__mark:hover{background:var(--robbo-nt-surface);',
    'border-color:var(--robbo-nt-green)}',
    '.robbo-nt-panel.robbo-nt-panel .robbo-nt__mark:focus{outline:none}',
    '.robbo-nt-panel.robbo-nt-panel .robbo-nt__mark:focus-visible{outline:2px solid var(--robbo-nt-green)}',
    '.robbo-nt-panel.robbo-nt-panel .robbo-nt__mark[disabled]{cursor:progress;opacity:.5}',
    '.robbo-nt-panel .robbo-nt__mark svg{display:block;pointer-events:none}',
    '.robbo-nt-panel .robbo-nt__summary.is-error{color:#b42318;font-weight:700}',
    '.robbo-nt-panel .robbo-nt__body{border-top:1px solid var(--robbo-nt-line);flex:1 1 auto;min-height:0;',
    'overflow-y:auto;overscroll-behavior:contain;padding:0 8px 8px;scrollbar-color:#d5d8dc transparent;',
    'scrollbar-width:thin}',
    '.robbo-nt-panel .robbo-nt__day + .robbo-nt__day{margin-top:4px}',
    '.robbo-nt-panel .robbo-nt__date{background:var(--robbo-nt-surface);color:var(--robbo-nt-text);',
    'font-family:inherit;font-size:13px;font-weight:800;letter-spacing:.04em;line-height:1.3;margin:0;',
    'padding:14px 12px 8px;position:sticky;text-transform:uppercase;top:0;z-index:1}',
    '.robbo-nt-panel .robbo-nt__entries{display:flex;flex-direction:column;gap:2px;list-style:none;margin:0;padding:0}',
    '.robbo-nt-panel .robbo-nt__entries > li{margin:0;padding:0;position:relative}',
    '.robbo-nt-panel .robbo-nt__entry{border-radius:12px;color:inherit;display:flex;gap:12px;margin:0;',
    'padding:10px 12px;position:relative;text-decoration:none;transition:background-color .15s ease}',
    '.robbo-nt-panel a.robbo-nt__entry:hover{background:var(--robbo-nt-hover);color:inherit;text-decoration:none}',
    '.robbo-nt-panel .robbo-nt__entry.is-unread{background:var(--robbo-nt-green-tint)}',
    '.robbo-nt-panel .robbo-nt__entry.has-mark{padding-right:48px}',
    '.robbo-nt-panel a.robbo-nt__entry.is-unread:hover{background:var(--robbo-nt-green-soft)}',
    '.robbo-nt-panel a.robbo-nt__entry:focus{outline:none}',
    '.robbo-nt-panel a.robbo-nt__entry:focus-visible{outline:2px solid var(--robbo-nt-green);outline-offset:-2px}',
    '.robbo-nt-panel .robbo-nt__kind{align-items:center;background:var(--robbo-nt-green-tint);border-radius:10px;',
    'color:var(--robbo-nt-green-dark);display:inline-flex;flex:0 0 auto;height:32px;justify-content:center;',
    'margin-top:1px;width:32px}',
    '.robbo-nt-panel .robbo-nt__entry.is-unread .robbo-nt__kind{background:var(--robbo-nt-surface)}',
    '.robbo-nt-panel .robbo-nt__kind svg{display:block}',
    '.robbo-nt-panel .robbo-nt__content{flex:1 1 auto;min-width:0}',
    '.robbo-nt-panel .robbo-nt__type{color:var(--robbo-nt-green-dark);display:block;font-size:12px;font-weight:700;',
    'line-height:1.3;margin:0 0 2px}',
    '.robbo-nt-panel .robbo-nt__dot{background:var(--robbo-nt-green);border-radius:50%;display:inline-block;',
    'height:8px;margin:0 6px 1px 0;vertical-align:middle;width:8px}',
    '.robbo-nt-panel .robbo-nt__text{-webkit-box-orient:vertical;-webkit-line-clamp:3;color:var(--robbo-nt-text);',
    'display:-webkit-box;font-size:14px;line-height:1.45;margin:0;overflow:hidden;overflow-wrap:anywhere}',
    '.robbo-nt-panel .robbo-nt__text strong{font-weight:700}',
    '.robbo-nt-panel .robbo-nt__meta{color:var(--robbo-nt-grey);display:flex;flex-wrap:wrap;font-size:12px;',
    'gap:2px 8px;line-height:1.3;margin:6px 0 0}',
    '.robbo-nt-panel .robbo-nt__course{min-width:0;overflow-wrap:anywhere}',
    '.robbo-nt-panel .robbo-nt__foot{border-top:1px solid var(--robbo-nt-line);padding:8px}',
    '.robbo-nt-panel a.robbo-nt__all{align-items:center;border-radius:10px;color:var(--robbo-nt-green-dark);',
    'display:flex;font-size:15px;font-weight:700;gap:6px;justify-content:center;min-height:44px;',
    'text-decoration:none;transition:background-color .15s ease}',
    '.robbo-nt-panel a.robbo-nt__all:hover{background:var(--robbo-nt-green-tint);color:var(--robbo-nt-green-dark)}',
    '.robbo-nt-panel a.robbo-nt__all svg{transition:transform .15s ease}',
    '.robbo-nt-panel a.robbo-nt__all:hover svg{transform:translateX(2px)}',
    '.robbo-nt-panel a.robbo-nt__all:focus-visible{outline:2px solid var(--robbo-nt-green);outline-offset:2px}',
    '.robbo-nt-panel .robbo-nt__note{align-items:center;color:var(--robbo-nt-muted);display:flex;flex-direction:column;',
    'font-size:15px;gap:8px;padding:32px 16px;text-align:center}',
    '.robbo-nt-panel .robbo-nt__note p{margin:0}',
    '.robbo-nt-panel .robbo-nt__note-title{color:var(--robbo-nt-text);font-weight:700}',
    '.robbo-nt-panel .robbo-nt__note svg{color:var(--robbo-nt-green)}',
    '.robbo-nt-panel .robbo-nt__skeleton{display:flex;gap:12px;padding:12px}',
    '.robbo-nt-panel .robbo-nt__skeleton i{animation:robbo-nt-shimmer 1.2s ease-in-out infinite;',
    'background:var(--robbo-nt-chip);border-radius:8px;display:block;height:12px}',
    '.robbo-nt-panel .robbo-nt__skeleton > i{border-radius:10px;flex:0 0 32px;height:32px}',
    '.robbo-nt-panel .robbo-nt__skeleton span{display:flex;flex:1 1 auto;flex-direction:column;gap:8px;',
    'padding-top:4px}',
    '.robbo-nt-panel .robbo-nt__skeleton span i:nth-child(1){width:40%}',
    '.robbo-nt-panel .robbo-nt__skeleton span i:nth-child(2){width:95%}',
    '.robbo-nt-panel .robbo-nt__skeleton span i:nth-child(3){width:55%}',
    '@keyframes robbo-nt-shimmer{50%{opacity:.45}}',
    '.robbo-nt-panel .robbo-nt__sr{border:0;clip:rect(0 0 0 0);height:1px;margin:-1px;overflow:hidden;padding:0;',
    'position:absolute;white-space:nowrap;width:1px}',
    '@media (hover:hover){.robbo-nt-panel .robbo-nt__entries > li .robbo-nt__mark{opacity:.55}',
    '.robbo-nt-panel .robbo-nt__entries > li:hover .robbo-nt__mark,',
    '.robbo-nt-panel .robbo-nt__entries > li .robbo-nt__mark:focus-visible{opacity:1}}',
    '@media (prefers-reduced-motion:reduce){.robbo-nt-panel,.robbo-nt .robbo-nt__badge,',
    '.robbo-nt-panel .robbo-nt__skeleton i{animation:none;transition:none}}',
    'body.indigo-dark-theme .robbo-nt-panel{--robbo-nt-surface:#1b2a22;--robbo-nt-text:#f8f8f8;',
    '--robbo-nt-muted:#c8d5cd;--robbo-nt-line:#3a4a41;--robbo-nt-hover:#24382d;--robbo-nt-chip:#2c3b33;',
    '--robbo-nt-green-dark:#86efac;--robbo-nt-green-tint:#173524;--robbo-nt-green-soft:#14532d;--robbo-nt-head:#173524}'
  ].join('');

  function ensureStyle() {
    if (document.getElementById(STYLE_ID)) {
      return;
    }
    var style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = CSS;
    document.head.appendChild(style);
  }

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) {
      node.className = className;
    }
    if (text !== undefined && text !== null) {
      node.textContent = text;
    }
    return node;
  }

  function prefersReducedMotion() {
    return window.matchMedia(REDUCED_MOTION_QUERY).matches;
  }

  function parseHtml(html) {
    return new DOMParser().parseFromString(String(html || ''), 'text/html');
  }

  function htmlToText(html) {
    if (!html) {
      return '';
    }
    return (parseHtml(html).body.textContent || '').replace(/\s+/g, ' ').trim();
  }

  // LMS HTML of unknown types → text nodes with <strong>/<em>/<br> rebuilt by us; nothing else survives.
  function safeHtmlInto(target, html) {
    function walk(node, parent) {
      if (node.nodeType === 3) {
        parent.appendChild(document.createTextNode(node.textContent));
        return;
      }
      if (node.nodeType !== 1) {
        return;
      }
      var tag = node.tagName;
      var into = parent;
      if (tag === 'STRONG' || tag === 'B') {
        into = parent.appendChild(el('strong'));
      } else if (tag === 'EM' || tag === 'I') {
        into = parent.appendChild(el('em'));
      } else if (tag === 'BR') {
        parent.appendChild(el('br'));
        return;
      }
      Array.prototype.forEach.call(node.childNodes, function (child) { walk(child, into); });
    }
    Array.prototype.forEach.call(parseHtml(html).body.childNodes, function (child) { walk(child, target); });
  }

  function renderText(target, texts, notification) {
    var context = notification.content_context || {};
    var type = notification.notification_type;
    if (type === 'course_updates') {
      target.textContent = htmlToText(context.course_update_content || notification.content);
      return;
    }
    var message = texts.messages[type];
    if (!message) {
      safeHtmlInto(target, notification.content);
      return;
    }
    message(context).forEach(function (part) {
      if (part && typeof part === 'object') {
        target.appendChild(el('strong', null, part.b === undefined || part.b === null ? '' : String(part.b)));
      } else {
        target.appendChild(document.createTextNode(String(part === undefined || part === null ? '' : part)));
      }
    });
  }

  function request(state, path, options) {
    options = options || {};
    var headers = {Accept: 'application/json'};
    if (options.token) {
      headers['X-CSRFToken'] = options.token;
    }
    if (options.body) {
      headers['Content-Type'] = 'application/json';
    }
    var url = state.lmsUrl + (path.charAt(0) === '/' ? path : API + path);
    return fetch(url, {
      method: options.method || 'GET',
      credentials: 'include',
      headers: headers,
      body: options.body ? JSON.stringify(options.body) : undefined,
    }).then(function (response) {
      if (!response.ok) {
        var error = new Error('HTTP ' + response.status);
        error.status = response.status;
        throw error;
      }
      return response.status === 204 ? {} : response.json();
    });
  }

  function csrfToken(state) {
    if (!state.tokenPromise) {
      state.tokenPromise = fetch(state.lmsUrl + '/csrf/api/v1/token', {credentials: 'include'})
        .then(function (response) { return response.json(); })
        .then(function (data) { return data.csrfToken; })
        .catch(function (error) {
          state.tokenPromise = null;
          throw error;
        });
    }
    return state.tokenPromise;
  }

  function setUnread(state, count) {
    state.unread = count;
    state.badge.hidden = !count;
    state.badge.textContent = count > 9 ? '9+' : String(count || '');
    var label = count ? state.texts.buttonUnread.replace('{count}', String(count)) : state.texts.title;
    state.button.setAttribute('aria-label', label);
    state.button.title = label;
  }

  function loadStatus(state) {
    return request(state, 'count/').then(function (data) {
      state.byApp = data.count_by_app_name || {};
      state.container.hidden = !data.show_notifications_tray;
      setUnread(state, Number(data.count) || 0);
      return data;
    }).catch(function () {
      // Guests (401), accounts not activated yet and a broken API: no button at all.
      state.container.hidden = true;
      if (state.isOpen) {
        close(state, false);
      }
    });
  }

  function dayLabel(state, date) {
    var start = new Date();
    start.setHours(0, 0, 0, 0);
    var day = new Date(date.getTime());
    day.setHours(0, 0, 0, 0);
    var diff = Math.round((start - day) / 86400000);
    if (diff === 0) {
      return state.texts.today;
    }
    if (diff === 1) {
      return state.texts.yesterday;
    }
    var options = {day: 'numeric', month: 'long'};
    if (day.getFullYear() !== start.getFullYear()) {
      options.year = 'numeric';
    }
    return date.toLocaleDateString(state.lang, options);
  }

  function isPlainLeftClick(event) {
    return event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey;
  }

  function markRead(state, notification) {
    return csrfToken(state).then(function (token) {
      return request(state, 'read/', {method: 'PATCH', token: token, body: {notification_id: notification.id}});
    });
  }

  function announceRead(detail) {
    window.dispatchEvent(new CustomEvent(READ_EVENT, {detail: detail}));
  }

  // The line under the title tells what happened: «Все уведомления прочитаны» or an error for a while.
  function showStatus(state, text, isError) {
    window.clearTimeout(state.statusTimer);
    state.summary.textContent = text;
    state.summary.classList.remove('has-unread');
    state.summary.classList.toggle('is-error', Boolean(isError));
    if (isError) {
      state.statusTimer = window.setTimeout(function () { renderSummary(state, state.unread); }, 4000);
    }
  }

  // An entry shown as read: no tint, dot or tick (the server already knows, or is being told).
  function showRead(entry) {
    entry.unread = false;
    entry.item.classList.remove('is-unread', 'has-mark');
    if (entry.marker) {
      entry.marker.remove();
      entry.marker = null;
    }
    if (entry.mark) {
      entry.mark.remove();
      entry.mark = null;
    }
  }

  function refreshReadAll(state) {
    var left = state.entries.some(function (entry) { return entry.unread; });
    state.readAll.hidden = !left;
  }

  function readOne(state, entry) {
    if (!entry.unread || entry.busy) {
      return;
    }
    entry.busy = true;
    var mark = entry.mark;
    var hadFocus = document.activeElement === mark;
    mark.disabled = true;
    markRead(state, entry.notification).then(function () {
      showRead(entry);
      refreshReadAll(state);
      announceRead({ids: [entry.notification.id]});
      // Keyboard users keep their place: the next unread entry's tick, or this entry.
      if (hadFocus) {
        var next = state.entries.filter(function (other) { return other.unread && other.mark; })
          .filter(function (other) {
            return entry.item.compareDocumentPosition(other.item) & Node.DOCUMENT_POSITION_FOLLOWING;
          })[0];
        (next ? next.mark : entry.item).focus({preventScroll: true});
      }
    }).catch(function () {
      mark.disabled = false;
      showStatus(state, state.texts.readError, true);
    }).then(function () { entry.busy = false; });
  }

  function readAll(state) {
    var button = state.readAll;
    if (button.disabled) {
      return;
    }
    button.disabled = true;
    csrfToken(state).then(function (token) {
      return request(state, READ_ALL_PATH, {method: 'POST', token: token});
    }).then(function () {
      state.entries.forEach(showRead);
      refreshReadAll(state);
      state.title.focus({preventScroll: true});
      showStatus(state, state.texts.readAllDone, false);
      announceRead({all: true});
      loadStatus(state);
    }).catch(function () {
      showStatus(state, state.texts.readError, true);
    }).then(function () { button.disabled = false; });
  }

  function renderEntry(state, notification) {
    var texts = state.texts;
    var unread = !notification.last_read;
    var url = notification.content_url;
    var item = el(url ? 'a' : 'div', 'robbo-nt__entry' + (unread ? ' is-unread has-mark' : ''));
    var entry = {notification: notification, item: item, unread: unread, marker: null, mark: null, busy: false};
    state.entries.push(entry);
    if (url) {
      item.href = url;
      item.addEventListener('click', function (event) {
        if (!entry.unread) {
          return;
        }
        showRead(entry);
        var reading = markRead(state, notification).catch(function () {});
        if (isPlainLeftClick(event)) {
          event.preventDefault();
          reading.then(function () { window.location.assign(url); });
        }
      });
    }
    var type = notification.notification_type;
    // learner_* types share one label and icon.
    var group = notification.app_name === 'learner_progress' && !TYPE_ICONS[type] ? 'learner_progress' : type;
    var kind = el('span', 'robbo-nt__kind');
    kind.setAttribute('aria-hidden', 'true');
    kind.innerHTML = TYPE_ICONS[group] || TYPE_ICONS.discussion;
    item.appendChild(kind);

    var content = el('span', 'robbo-nt__content');
    var label = el('span', 'robbo-nt__type');
    if (unread) {
      entry.marker = el('span');
      entry.marker.appendChild(el('span', 'robbo-nt__dot')).setAttribute('aria-hidden', 'true');
      entry.marker.appendChild(el('span', 'robbo-nt__sr', texts.unread + ': '));
      label.appendChild(entry.marker);
    }
    label.appendChild(document.createTextNode(texts.types[group] || texts.types.other));
    content.appendChild(label);
    var text = el('span', 'robbo-nt__text');
    renderText(text, texts, notification);
    content.appendChild(text);
    var meta = el('span', 'robbo-nt__meta');
    var course = (notification.content_context || {}).course_name || notification.course_name;
    if (course) {
      meta.appendChild(el('span', 'robbo-nt__course', course));
    }
    var created = new Date(notification.created);
    if (!isNaN(created.getTime())) {
      var time = el('time', null, created.toLocaleTimeString(state.lang, {hour: '2-digit', minute: '2-digit'}));
      time.setAttribute('datetime', notification.created);
      meta.appendChild(time);
    }
    content.appendChild(meta);
    item.appendChild(content);
    var row = el('li');
    row.appendChild(item);
    if (unread) {
      // A sibling of the entry, not inside it: the entry is a link.
      entry.mark = el('button', 'robbo-nt__mark');
      entry.mark.type = 'button';
      entry.mark.innerHTML = ICON_CHECK;
      entry.mark.setAttribute('aria-label', texts.markRead);
      entry.mark.title = texts.markRead;
      entry.mark.addEventListener('click', function () { readOne(state, entry); });
      row.appendChild(entry.mark);
    }
    return row;
  }

  function renderNote(state, title, body, withIcon) {
    var note = el('div', 'robbo-nt__note');
    if (withIcon) {
      note.insertAdjacentHTML('beforeend', ICON_EMPTY);
    }
    note.appendChild(el('p', 'robbo-nt__note-title', title));
    if (body) {
      note.appendChild(el('p', null, body));
    }
    state.body.textContent = '';
    state.body.appendChild(note);
  }

  function renderSkeleton(state) {
    state.body.textContent = '';
    for (var i = 0; i < 3; i += 1) {
      var row = el('div', 'robbo-nt__skeleton');
      row.setAttribute('aria-hidden', 'true');
      row.innerHTML = '<i></i><span><i></i><i></i><i></i></span>';
      state.body.appendChild(row);
    }
    state.body.appendChild(el('p', 'robbo-nt__sr', state.texts.loading));
  }

  function renderSummary(state, count) {
    window.clearTimeout(state.statusTimer);
    state.summary.classList.remove('is-error');
    state.summary.textContent = count ? state.texts.summaryNew(count) : state.texts.summaryNone;
    state.summary.classList.toggle('has-unread', Boolean(count));
  }

  function renderList(state, results) {
    if (!results.length) {
      state.entries = [];
      refreshReadAll(state);
      renderNote(state, state.texts.emptyTitle, state.texts.emptyBody, true);
      return;
    }
    state.body.textContent = '';
    state.entries = [];
    var day = null;
    var list = null;
    results.forEach(function (notification) {
      var label = dayLabel(state, new Date(notification.created));
      if (label !== day) {
        day = label;
        var section = el('section', 'robbo-nt__day');
        section.appendChild(el('h3', 'robbo-nt__date', label));
        list = el('ul', 'robbo-nt__entries');
        section.appendChild(list);
        state.body.appendChild(section);
      }
      list.appendChild(renderEntry(state, notification));
    });
    refreshReadAll(state);
  }

  function place(state) {
    var rect = state.button.getBoundingClientRect();
    var viewport = document.documentElement.clientWidth;
    var top = Math.round(rect.bottom + 10);
    var panel = state.panel;
    var panelLeft = 8;
    panel.style.top = top + 'px';
    if (window.matchMedia(NARROW_QUERY).matches) {
      panel.style.left = '8px';
      panel.style.right = '8px';
      panel.style.width = 'auto';
    } else {
      var right = Math.max(8, Math.round(viewport - rect.right - 4));
      panel.style.left = 'auto';
      panel.style.right = right + 'px';
      panel.style.width = '';
      // From the layout box: getBoundingClientRect() is still shifted by the opening scale(.98).
      panelLeft = viewport - right - panel.offsetWidth;
    }
    panel.style.maxHeight = Math.max(240, window.innerHeight - top - 12) + 'px';
    // The caret points at the middle of the button wherever the panel ends up (left is inside the 1px border).
    panelLeft += 1;
    panel.style.setProperty('--robbo-nt-caret', Math.round(rect.left + rect.width / 2 - panelLeft - 7) + 'px');
  }

  function buildPanel(state) {
    var panel = el('div', 'robbo-nt-panel');
    panel.id = 'robbo-nt-panel-' + state.id;
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-labelledby', panel.id + '-title');
    panel.hidden = true;
    panel.appendChild(el('span', 'robbo-nt__caret')).setAttribute('aria-hidden', 'true');

    var head = el('div', 'robbo-nt__head');
    var heading = el('div');
    state.title = el('h2', 'robbo-nt__title', state.texts.title);
    state.title.id = panel.id + '-title';
    state.title.tabIndex = -1;
    state.summary = el('p', 'robbo-nt__summary', '');
    heading.appendChild(state.title);
    heading.appendChild(state.summary);
    state.close = el('button', 'robbo-nt__close');
    state.close.type = 'button';
    state.close.innerHTML = ICON_CLOSE;
    state.close.setAttribute('aria-label', state.texts.close);
    state.close.addEventListener('click', function () { close(state, true); });
    state.readAll = el('button', 'robbo-nt__read-all');
    state.readAll.type = 'button';
    state.readAll.innerHTML = ICON_CHECK_ALL;
    state.readAll.appendChild(document.createTextNode(state.texts.readAll));
    state.readAll.hidden = true;
    state.readAll.addEventListener('click', function () { readAll(state); });
    var actions = el('div', 'robbo-nt__actions');
    actions.appendChild(state.readAll);
    actions.appendChild(state.close);
    head.appendChild(heading);
    head.appendChild(actions);

    state.summary.setAttribute('aria-live', 'polite');
    state.body = el('div', 'robbo-nt__body');
    var foot = el('div', 'robbo-nt__foot');
    state.all = el('a', 'robbo-nt__all', state.texts.all);
    state.all.insertAdjacentHTML('beforeend', ICON_ARROW);
    state.all.href = state.feedUrl;
    foot.appendChild(state.all);
    panel.appendChild(head);
    panel.appendChild(state.body);
    panel.appendChild(foot);
    document.body.appendChild(panel);
    state.panel = panel;
    state.button.setAttribute('aria-controls', panel.id);
  }

  function markSeen(state) {
    var apps = Object.keys(state.byApp || {}).filter(function (app) { return state.byApp[app] > 0; });
    if (!apps.length) {
      return;
    }
    csrfToken(state).then(function (token) {
      return Promise.all(apps.map(function (app) {
        return request(state, 'mark-seen/' + encodeURIComponent(app) + '/', {method: 'PUT', token: token});
      }));
    }).then(function () {
      state.byApp = {};
      setUnread(state, 0);
    }).catch(function () { /* stays new until the next open */ });
  }

  function onDocumentPointer(state, event) {
    if (!state.panel.contains(event.target) && !state.button.contains(event.target)) {
      close(state, false);
    }
  }

  function onKey(state, event) {
    if (event.key === 'Escape') {
      close(state, true);
    }
  }

  function open(state) {
    if (!state.panel) {
      buildPanel(state);
    }
    window.clearTimeout(state.closeTimer);
    state.isOpen = true;
    state.panel.hidden = false;
    state.button.setAttribute('aria-expanded', 'true');
    renderSummary(state, state.unread);
    place(state);
    window.requestAnimationFrame(function () {
      if (state.isOpen) {
        state.panel.classList.add('is-open');
      }
    });
    document.addEventListener('pointerdown', state.listeners.pointer, true);
    document.addEventListener('keydown', state.listeners.key);
    window.addEventListener('resize', state.listeners.place);
    window.addEventListener('scroll', state.listeners.place, true);
    state.title.focus({preventScroll: true});
    // Fresh list on every open; the previous one stays on screen while it loads.
    if (!state.loaded) {
      renderSkeleton(state);
    }
    var load = request(state, '?page_size=' + PAGE_SIZE);
    load.then(function (data) {
      state.loaded = true;
      renderList(state, data.results || []);
      if (state.isOpen) {
        place(state);
      }
      markSeen(state);
    }).catch(function () {
      renderNote(state, state.texts.error, null, false);
    });
  }

  function close(state, returnFocus) {
    if (!state.isOpen) {
      return;
    }
    state.isOpen = false;
    state.panel.classList.remove('is-open');
    state.button.setAttribute('aria-expanded', 'false');
    document.removeEventListener('pointerdown', state.listeners.pointer, true);
    document.removeEventListener('keydown', state.listeners.key);
    window.removeEventListener('resize', state.listeners.place);
    window.removeEventListener('scroll', state.listeners.place, true);
    state.closeTimer = window.setTimeout(function () {
      if (!state.isOpen) {
        state.panel.hidden = true;
      }
    }, prefersReducedMotion() ? 0 : CLOSE_DELAY);
    if (returnFocus) {
      state.button.focus();
    }
  }

  function mount(container, options) {
    if (!container || container.getAttribute('data-robbo-nt-mounted')) {
      return null;
    }
    options = options || {};
    ensureStyle();
    container.setAttribute('data-robbo-nt-mounted', '1');
    container.classList.add('robbo-nt', 'robbo-nt--' + (options.variant || 'on-dark'));
    counter += 1;
    var lmsUrl = String(options.lmsUrl || window.location.origin).replace(/\/+$/, '');
    var lang = String(options.lang || document.documentElement.lang || 'ru').toLowerCase().split('-')[0];
    var state = {
      id: counter,
      container: container,
      lmsUrl: lmsUrl,
      lang: lang,
      texts: TEXTS[lang] || TEXTS.en,
      feedUrl: options.feedUrl || lmsUrl + '/account/notifications',
      unread: 0,
      byApp: {},
      entries: [],
      statusTimer: null,
      isOpen: false,
      loaded: false,
      closeTimer: null,
    };
    state.listeners = {
      pointer: function (event) { onDocumentPointer(state, event); },
      key: function (event) { onKey(state, event); },
      place: function () { place(state); },
      changed: function () { loadStatus(state); },
      visibility: function () {
        if (document.visibilityState === 'visible') {
          loadStatus(state);
        }
      },
    };
    state.button = el('button', 'robbo-nt__button');
    state.button.type = 'button';
    state.button.innerHTML = ICON_BELL;
    state.button.setAttribute('aria-haspopup', 'dialog');
    state.button.setAttribute('aria-expanded', 'false');
    state.badge = el('span', 'robbo-nt__badge');
    state.badge.setAttribute('aria-hidden', 'true');
    state.badge.hidden = true;
    state.button.appendChild(state.badge);
    state.button.addEventListener('click', function () {
      if (state.isOpen) {
        close(state, false);
      } else {
        open(state);
      }
    });
    setUnread(state, 0);
    container.hidden = true;
    container.appendChild(state.button);
    window.addEventListener(CHANGED_EVENT, state.listeners.changed);
    document.addEventListener('visibilitychange', state.listeners.visibility);
    loadStatus(state);
    return {
      unmount: function () {
        close(state, false);
        window.clearTimeout(state.closeTimer);
        window.clearTimeout(state.statusTimer);
        window.removeEventListener(CHANGED_EVENT, state.listeners.changed);
        document.removeEventListener('visibilitychange', state.listeners.visibility);
        if (state.panel) {
          state.panel.remove();
        }
        container.textContent = '';
        container.removeAttribute('data-robbo-nt-mounted');
      },
    };
  }

  function autoMount() {
    var nodes = document.querySelectorAll('[data-robbo-notifications]:not([data-robbo-nt-mounted])');
    Array.prototype.forEach.call(nodes, function (node) {
      mount(node, {
        lmsUrl: node.getAttribute('data-lms-url'),
        lang: node.getAttribute('data-lang'),
        variant: node.getAttribute('data-variant'),
        feedUrl: node.getAttribute('data-feed-url'),
      });
    });
  }

  window.RobboNotifications = {mount: mount};

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', autoMount);
  } else {
    autoMount();
  }
}());
