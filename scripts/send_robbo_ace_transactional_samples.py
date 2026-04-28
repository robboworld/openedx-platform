# Отправка транзакционных ACE-писем теми же кодовыми путями, что и в проде (без подмены
# получателя и без фиктивных ключей в ссылках).
#
# Запуск в контейнере LMS (Tutor):
#   ./manage.py lms shell < scripts/send_robbo_ace_transactional_samples.py
#
# Переменные окружения (опционально):
#   SEND_ACE_USER_ID           — id пользователя (по умолчанию 69)
#   SEND_ACE_PAUSE_SEC          — пауза между письмами, сек (по умолчанию 5)
#   SEND_ACE_NEW_EMAIL          — новый primary email (должен быть свободен в БД и ≠ текущему).
#                                Без него письмо «смена email» и связанное pending не создаём.
#   SEND_ACE_SECONDARY_EMAIL    — email для письма RecoveryEmailCreate (secondary / восстановление).
#                                Без него шаг пропускается. Должен проходить validate_secondary_email.
#
# Письмо EmailChangeConfirmation (текст «вы сменили email…») в Open edX уходит только после
# перехода по ссылке из письма смены email — его нужно получить, открыв ссылку из входящего
# письма SEND_ACE_NEW_EMAIL (скрипт её специально не дублирует).

import os
import time

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.test.client import RequestFactory

from edx_ace import ace

from common.djangoapps.student.forms import send_account_recovery_email_for_user
from common.djangoapps.student.views.management import (
    do_email_change_request,
    validate_new_email,
    validate_secondary_email,
    compose_activation_email,
)
from openedx.core.djangoapps.user_authn.views.password_reset import (
    send_password_reset_email_for_user,
    send_password_reset_success_email,
)
from openedx.core.lib.celery.task_utils import emulate_http_request

USER_ID = int(os.environ.get("SEND_ACE_USER_ID", "69"))
PAUSE_SEC = int(os.environ.get("SEND_ACE_PAUSE_SEC", "5"))
NEW_EMAIL = os.environ.get("SEND_ACE_NEW_EMAIL", "").strip()
SECONDARY_EMAIL = os.environ.get("SEND_ACE_SECONDARY_EMAIL", "").strip()


def _pause():
    time.sleep(PAUSE_SEC)


def _request(site, user):
    rf = RequestFactory()
    req = rf.get("/")
    use_https = getattr(settings, "ENABLE_HTTPS", False)
    req.is_secure = lambda: use_https
    req.site = site
    req.user = user
    return req


def main():
    user = User.objects.get(id=USER_ID)
    site = Site.objects.get_current()
    request = _request(site, user)

    with emulate_http_request(site=site, user=user):
        # 1. Активация учётной записи — тот же compose, что и при регистрации (получатель: user.email)
        msg = compose_activation_email(user, route_enabled=False)
        ace.send(msg)
        print("OK AccountActivation ->", msg.recipient.email_address)
        _pause()

        # 2. Сброс пароля
        send_password_reset_email_for_user(user, request)
        print("OK PasswordReset ->", user.email)
        _pause()

        # 3. Успешный сброс пароля (как send_password_reset_success_email)
        send_password_reset_success_email(user, request)
        print("OK PasswordResetSuccess ->", user.email)
        _pause()

        # 4. Восстановление доступа (письмо с is_account_recovery=true)
        send_account_recovery_email_for_user(user, request, email=user.email)
        print("OK AccountRecovery ->", user.email)
        _pause()

        if NEW_EMAIL:
            validate_new_email(user, NEW_EMAIL)
            if User.objects.filter(email__iexact=NEW_EMAIL).exclude(pk=user.pk).exists():
                raise ValueError(f"Email уже занят другим пользователем: {NEW_EMAIL}")
            do_email_change_request(user, NEW_EMAIL, secondary_email_change_request=False)
            print("OK EmailChange (pending + письмо на новый адрес) ->", NEW_EMAIL)
            _pause()
        else:
            print("Skip EmailChange: задайте SEND_ACE_NEW_EMAIL (свободный в БД адрес).")

        if SECONDARY_EMAIL:
            validate_secondary_email(user, SECONDARY_EMAIL)
            do_email_change_request(user, SECONDARY_EMAIL, secondary_email_change_request=True)
            print("OK RecoveryEmailCreate ->", SECONDARY_EMAIL)
            _pause()
        else:
            print("Skip RecoveryEmailCreate: задайте SEND_ACE_SECONDARY_EMAIL.")

        print(
            "Готово. Письмо «Подтверждение смены email» (EmailChangeConfirmation) "
            "придёт на старый и новый адрес только после открытия ссылки из письма на",
            NEW_EMAIL or "(не отправляли — не задан SEND_ACE_NEW_EMAIL)",
            ".",
        )


main()
