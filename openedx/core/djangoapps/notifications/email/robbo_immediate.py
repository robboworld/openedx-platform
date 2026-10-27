"""
Robbo: email notifications with the «Сразу» (Immediately) cadence.

Teak keeps ``EmailCadence.IMMEDIATELY`` as a value but sends only daily/weekly digests. Here
``send_notifications`` (tasks.py) hands over the users whose preference for that type is email +
Immediately, and every new notification goes out as its own short letter in the recipient's
language (texts: ``robbo_texts.py``). Users with the one-click unsubscribe, disabled accounts and
users without the email waffle flag get nothing, as with digests.

Copyright (C) 2026 Robbo <https://robbo.ru>
SPDX-License-Identifier: AGPL-3.0-only
Part of the Robbo Open edX distribution. See NOTICE at repository root.
"""
import logging

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.utils.html import escape
from edx_django_utils.monitoring import set_code_owner_attribute
from opaque_keys.edx.keys import CourseKey

from openedx.core.djangoapps.notifications.email import ONE_CLICK_EMAIL_UNSUB_KEY
from openedx.core.djangoapps.notifications.email.robbo_layout import (
    GREEN_DARK, MUTED, TEXT, button, frame, settings_url,
)
from openedx.core.djangoapps.notifications.email.utils import is_email_notification_flag_enabled
from openedx.core.djangoapps.notifications.email_notifications import EmailCadence
from openedx.core.djangoapps.notifications.models import Notification
from openedx.core.djangoapps.notifications.robbo_texts import (
    lang_of, notification_from_email, notification_html, notification_text, type_label,
)
from openedx.core.djangoapps.user_api.models import UserPreference

log = logging.getLogger(__name__)
User = get_user_model()

FOOTER = {
    'ru': ('Вы получили это письмо, потому что в настройках уведомлений выбрали письма «сразу».',
           'Настроить уведомления', 'Открыть'),
    'en': ('You get this email because your notification settings send these letters immediately.',
           'Notification settings', 'Open'),
}


def type_cadence(preference, app_name, notification_type):
    """Email cadence the user chose for this type (core types share the app's «core» entry)."""
    app = (preference.notification_preference_config or {}).get(app_name, {})
    types = app.get('notification_types', {})
    if notification_type in app.get('core_notification_types', []):
        return types.get('core', {}).get('email_cadence')
    return types.get(notification_type, {}).get('email_cadence')


def immediate_recipients(preferences, app_name, notification_type):
    """Users whose email for this type is on with the Immediately cadence."""
    return [
        preference.user_id for preference in preferences
        if 'email' in preference.get_channels_for_notification_type(app_name, notification_type)
        and type_cadence(preference, app_name, notification_type) == EmailCadence.IMMEDIATELY
    ]


def _user_language(user):
    return UserPreference.get_value(user, 'pref-lang') or settings.LANGUAGE_CODE


def _render(notification, lang):
    body = notification_html(notification.notification_type, notification.content_context, lang)
    if not body:
        return None
    note, settings_label, open_label = FOOTER[lang]
    course = notification.content_context.get('course_name', '')
    inner = (
        f'<p style="margin:0 0 8px;color:{GREEN_DARK};font-size:13px;font-weight:700">'
        f'{escape(type_label(notification.notification_type, lang))}</p>'
        f'<p style="margin:0 0 8px;color:{TEXT};font-size:16px;line-height:1.5">{body}</p>'
        f'<p style="margin:0 0 20px;color:{MUTED};font-size:13px">{escape(course)}</p>'
        + (button(notification.content_url, open_label) if notification.content_url else '')
    )
    html = frame(lang, inner, note)
    text = '\n\n'.join(filter(None, [
        notification_text(notification.notification_type, notification.content_context, lang),
        course, notification.content_url, f'{settings_label}: {settings_url()}',
    ]))
    subject = f"{type_label(notification.notification_type, lang)}: {course}" if course else type_label(
        notification.notification_type, lang)
    return subject, text, html


@shared_task(ignore_result=True)
@set_code_owner_attribute
def send_immediate_notification_emails(user_ids, course_key, notification_type, created_after):
    """One letter per notification of this type created for these users since ``created_after``."""
    course_key = CourseKey.from_string(course_key)
    notifications = Notification.objects.filter(
        user_id__in=user_ids, course_id=course_key, notification_type=notification_type,
        email=True, created__gte=created_after,
    ).select_related('user')
    unsubscribed = set(UserPreference.objects.filter(
        user_id__in=user_ids, key=ONE_CLICK_EMAIL_UNSUB_KEY,
    ).values_list('user_id', flat=True))
    sent = 0
    for notification in notifications:
        user = notification.user
        if (
            not user.is_active or not user.has_usable_password() or user.id in unsubscribed
            or not user.email or not is_email_notification_flag_enabled(user)
        ):
            continue
        rendered = _render(notification, lang_of(_user_language(user)))
        if not rendered:
            continue
        subject, text, html = rendered
        message = EmailMultiAlternatives(subject, text, notification_from_email(), [user.email])
        message.attach_alternative(html, 'text/html')
        try:
            message.send()
            sent += 1
        except Exception:  # pylint: disable=broad-except
            log.exception('Robbo: immediate notification email %s to user %s failed', notification.id, user.id)
    log.info('Robbo: %s immediate %s emails sent for %s', sent, notification_type, course_key)
