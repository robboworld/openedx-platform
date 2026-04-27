"""
Robbo course-opening interest endpoint for /courses stub cards.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Iterable, List, Optional

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import send_mail
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from lms.djangoapps.courseware.robbo_catalog import get_robbo_catalog_stubs

log = logging.getLogger('robbo.course_interest')


def _json_error(message: str, status: int) -> JsonResponse:
    return JsonResponse({
        'ok': False,
        'message': message,
    }, status=status)


def _load_json_body(request) -> Dict[str, Any]:
    try:
        return json.loads(request.body.decode('utf-8') or '{}')
    except (TypeError, ValueError):
        return {}


def _get_stub(stub_id: str) -> Optional[Dict[str, Any]]:
    for stub in get_robbo_catalog_stubs():
        if stub.get('id') == stub_id:
            return stub
    return None


def _get_profile(user):
    try:
        return user.profile
    except ObjectDoesNotExist:
        return None


def _get_profile_meta(profile) -> Dict[str, Any]:
    if profile is None or not getattr(profile, 'meta', ''):
        return {}
    try:
        meta = json.loads(profile.meta)
    except (TypeError, ValueError):
        return {}
    if isinstance(meta, dict):
        return meta
    return {}


def _get_client_ip(request) -> str:
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def _normalize_recipients(recipients: Iterable[str]) -> List[str]:
    if isinstance(recipients, str):
        recipients = [recipients]
    return [email.strip() for email in recipients if email and email.strip()]


def build_course_interest_payload(request, stub: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a normalized interest payload.

    Current transports are email + structured log. A future DB model can persist
    this payload without changing the frontend API contract.
    """
    user = request.user
    profile = _get_profile(user)
    meta = _get_profile_meta(profile)
    full_name = (
        getattr(profile, 'name', '')
        or user.get_full_name()
        or ''
    ).strip()

    return {
        'course': {
            'stub_id': stub['id'],
            'title': stub['title'],
        },
        'learner': {
            'user_id': user.id,
            'username': user.username,
            'email': user.email,
            'full_name': full_name,
            'company': (meta.get('company') or '').strip(),
        },
        'request': {
            'ip': _get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
        },
        'submitted_at': timezone.now().isoformat(),
        'storage': 'email_and_log',
    }


def _build_email_body(payload: Dict[str, Any]) -> str:
    course = payload['course']
    learner = payload['learner']
    request_info = payload['request']

    return '\n'.join([
        'Пользователь подписался на уведомление об открытии курса.',
        '',
        f"Курс: {course['title']}",
        f"Stub ID: {course['stub_id']}",
        '',
        f"Email: {learner['email']}",
        f"ФИО: {learner['full_name'] or '-'}",
        f"Компания: {learner['company'] or '-'}",
        f"User ID: {learner['user_id']}",
        f"Username: {learner['username']}",
        '',
        f"Время: {payload['submitted_at']}",
        f"IP: {request_info['ip'] or '-'}",
        f"User-Agent: {request_info['user_agent'] or '-'}",
    ])


def _send_interest_email(payload: Dict[str, Any]) -> None:
    recipients = _normalize_recipients(getattr(settings, 'ROBBO_COURSE_INTEREST_RECIPIENTS', []))
    if not recipients:
        log.warning(
            'course_interest missing recipients: stub_id=%s user_id=%s email=%r',
            payload['course']['stub_id'],
            payload['learner']['user_id'],
            payload['learner']['email'],
            extra={'course_interest': payload},
        )
        raise RuntimeError('ROBBO_COURSE_INTEREST_RECIPIENTS is empty')

    send_mail(
        subject=f"Интерес к курсу: {payload['course']['title']}",
        message=_build_email_body(payload),
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
        recipient_list=recipients,
        fail_silently=False,
    )


@login_required
@require_POST
def course_interest(request) -> JsonResponse:
    data = _load_json_body(request)
    stub_id = data.get('stub_id')

    if not isinstance(stub_id, str) or not stub_id.strip():
        return _json_error('Не указан курс для подписки.', status=400)

    stub = _get_stub(stub_id.strip())
    if stub is None:
        return _json_error('Неизвестный курс для подписки.', status=400)

    payload = build_course_interest_payload(request, stub)

    try:
        _send_interest_email(payload)
    except Exception:  # pylint: disable=broad-except
        log.exception(
            'course_interest email failed: stub_id=%s user_id=%s email=%r',
            payload['course']['stub_id'],
            payload['learner']['user_id'],
            payload['learner']['email'],
            extra={'course_interest': payload},
        )
        return _json_error('Не удалось отправить заявку. Попробуйте ещё раз.', status=502)

    log.info(
        'course_interest submitted: stub_id=%s course_title=%r user_id=%s email=%r full_name=%r company=%r',
        payload['course']['stub_id'],
        payload['course']['title'],
        payload['learner']['user_id'],
        payload['learner']['email'],
        payload['learner']['full_name'],
        payload['learner']['company'],
        extra={'course_interest': payload},
    )
    return JsonResponse({
        'ok': True,
        'status': 'subscribed',
        'message': 'Мы сообщим на вашу почту, когда курс откроется.',
    })
