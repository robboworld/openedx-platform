# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (certificate designs). See NOTICE at repository root.
"""
The «certificate not shown» page (themes/robbo-theme/lms/templates/certificates/invalid.html and
server-error.html): the look of the human-readable error page (robbo_errors, docs/human-errors.md
§1 in the meta repo) with texts of its own.

A learner or a visitor always reads «Сертификат не найден»: they cannot fix anything themselves.
A Studio preview (``?preview=<mode>``) is opened by the course team, so it tells why the
certificate is not shown and links to the Studio page that fixes it (the wording follows the
«Сертификаты» checks of the instructor dashboard, readiness.py).
"""

from django.conf import settings

from lms.djangoapps.robbo_changelog.labels import current_lang, pick
from lms.djangoapps.robbo_errors.upstream_pages import build

from .readiness import studio_certificates_url

NOT_FOUND = 'not_found'
SITE_DISABLED = 'site_disabled'
COURSE_NOT_FOUND = 'course_not_found'
COURSE_DISABLED = 'course_disabled'
NO_PREVIEW_ACCESS = 'no_preview_access'
NOT_CREATED = 'not_created'
SERVER_ERROR = 'server_error'
URL_UNSUPPORTED = 'url_unsupported'

# Shown to everyone, preview or not
PUBLIC_REASONS = (NOT_FOUND, URL_UNSUPPORTED)

# reason: (error code of the catalog, title, message); {studio} — the Studio page link is offered
TEXTS = {
    NOT_FOUND: ('NOT-FOUND', {
        'ru': 'Сертификат не найден',
        'en': 'Certificate not found',
    }, {
        'ru': 'Возможно, в ссылке ошибка или сертификат ещё не выдан. '
              'Если вы прошли курс, откройте сертификат со страницы «Прогресс» в курсе.',
        'en': 'The link may have a mistake, or the certificate has not been issued yet. '
              'If you have completed the course, open the certificate from the course «Progress» page.',
    }),
    SITE_DISABLED: ('NOT-FOUND', {
        'ru': 'Сертификаты на сайте выключены',
        'en': 'Certificates are turned off on the site',
    }, {
        'ru': 'Показ сертификатов выключен в настройках сайта. Напишите в поддержку.',
        'en': 'Showing certificates is turned off in the site settings. Contact support.',
    }),
    COURSE_NOT_FOUND: ('NOT-FOUND', {
        'ru': 'Курс не найден',
        'en': 'Course not found',
    }, {
        'ru': 'Курса с таким кодом нет на сайте. Проверьте адрес страницы.',
        'en': 'There is no course with this code on the site. Check the page address.',
    }),
    COURSE_DISABLED: ('NOT-FOUND', {
        'ru': 'Сертификат курса не открывается как веб-страница',
        'en': 'The course certificate is not shown as a web page',
    }, {
        'ru': 'В дополнительных настройках курса включите «Разрешить выпуск HTML-сертификатов»: '
              'значение true, затем «Сохранить изменения».',
        'en': 'In the course Advanced Settings, set «Certificate Web/HTML View Enabled» to true and save the changes.',
    }),
    NO_PREVIEW_ACCESS: ('ACCESS-DENIED', {
        'ru': 'Нет доступа к предпросмотру сертификата',
        'en': 'No access to the certificate preview',
    }, {
        'ru': 'Предпросмотр видит только команда курса. Войдите под учётной записью из команды курса.',
        'en': 'Only the course team can preview the certificate. Sign in with a course team account.',
    }),
    NOT_CREATED: ('NOT-FOUND', {
        'ru': 'Сертификат не создан в редакторе курса',
        'en': 'The certificate is not created in Studio',
    }, {
        'ru': 'На странице «Сертификаты» в редакторе курса создайте сертификат и нажмите «Активировать».',
        'en': 'On the «Certificates» page in Studio, create a certificate and click «Activate».',
    }),
    URL_UNSUPPORTED: ('NOT-FOUND', {
        'ru': 'Ссылка на сертификат устарела',
        'en': 'The certificate link is out of date',
    }, {
        'ru': 'Сам сертификат действителен. Если он ваш, откройте его заново со страницы «Прогресс» в курсе '
              'и поделитесь новой ссылкой. Если чужой — попросите владельца прислать новую ссылку.',
        'en': 'The certificate itself is valid. If it is yours, open it again from the course «Progress» page '
              'and share the new link. If it is someone else\'s, ask the owner for a new link.',
    }),
    SERVER_ERROR: ('SRV-ERROR', {
        'ru': 'Не удалось собрать сертификат',
        'en': 'Couldn\'t build the certificate',
    }, {
        'ru': 'Проверьте на странице «Сертификаты» в редакторе курса подписи и их изображения. '
              'Если всё заполнено, напишите в поддержку и укажите код.',
        'en': 'Check the signatories and their images on the «Certificates» page in Studio. '
              'If everything is filled in, contact support and give the code.',
    }),
}

OPEN_CERTIFICATES = {'ru': 'Открыть сертификаты курса', 'en': 'Open course certificates'}
OPEN_ADVANCED = {'ru': 'Открыть дополнительные настройки', 'en': 'Open Advanced Settings'}


def studio_advanced_settings_url(course_key):
    authoring = (getattr(settings, 'MFE_CONFIG', None) or {}).get('COURSE_AUTHORING_MICROFRONTEND_URL')
    if authoring:
        return f'{authoring.rstrip("/")}/course/{course_key}/settings/advanced'
    return f'//{settings.CMS_BASE}/settings/advanced/{course_key}'


# Reasons the course team fixes in Studio: (page url, button label)
STUDIO_FIXES = {
    COURSE_DISABLED: (studio_advanced_settings_url, OPEN_ADVANCED),
    NOT_CREATED: (studio_certificates_url, OPEN_CERTIFICATES),
    SERVER_ERROR: (studio_certificates_url, OPEN_CERTIFICATES),
}


def error_context(request, course_id, reason=NOT_FOUND):
    """Context of ``robbo_errors/_error_block.html`` for a certificate that is not shown."""
    preview = bool(request is not None and request.GET.get('preview'))
    if not preview and reason not in PUBLIC_REASONS:
        reason = NOT_FOUND
    code, title, message = TEXTS.get(reason, TEXTS[NOT_FOUND])
    lang = current_lang()
    action_url = action_label = None
    if reason in STUDIO_FIXES and course_id:
        url, label = STUDIO_FIXES[reason]
        action_url, action_label = url(course_id), pick(label, lang)
    # handle_500 catches a failed preview before the robbo_errors middleware: build() journals it
    # (called inside its ``except``), so support finds the code shown on the page
    return {'robbo_error': build(
        request, code, pick(title, lang), pick(message, lang),
        action_url=action_url, action_label=action_label,
        journal=reason == SERVER_ERROR, developer_message='certificate preview failed',
    )}
