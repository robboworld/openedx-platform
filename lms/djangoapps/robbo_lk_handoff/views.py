# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
"""Bidirectional short-lived HMAC handoff between ЛК and Open edX."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlparse

from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, HttpResponseForbidden, HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

log = logging.getLogger(__name__)

HANDOFF_TTL_SECONDS = 90


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode('ascii').rstrip('=')


def _b64url_decode(value: str) -> bytes:
    pad = '=' * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + pad)


def _allowed_hosts() -> set[str]:
    allowed = {
        'localhost',
        '127.0.0.1',
        getattr(settings, 'LMS_BASE', '') or '',
    }
    lms_base = getattr(settings, 'LMS_ROOT_URL', '') or ''
    if lms_base:
        try:
            allowed.add(urlparse(lms_base).hostname or '')
        except Exception:  # pylint: disable=broad-except
            pass
    for attr in ('ROBBO_LK_FRONTEND_BASE', 'ROBBO_LK_BACKEND_BASE'):
        base = getattr(settings, attr, '') or ''
        if base:
            try:
                allowed.add(urlparse(base).hostname or '')
            except Exception:  # pylint: disable=broad-except
                pass
    return {h.lower() for h in allowed if h}


def _allowed_next(next_url: str) -> bool:
    if not next_url:
        return False
    parsed = urlparse(next_url)
    if parsed.scheme not in ('http', 'https'):
        return False
    host = (parsed.hostname or '').lower()
    return host in _allowed_hosts()


def _issue_token(email: str, secret: str) -> str:
    now = datetime.now(tz=timezone.utc)
    claims = {
        'email': email.strip().lower(),
        'nbf': int((now - timedelta(seconds=5)).timestamp()),
        'exp': int((now + timedelta(seconds=HANDOFF_TTL_SECONDS)).timestamp()),
    }
    payload_b64 = _b64url_encode(json.dumps(claims, separators=(',', ':')).encode('utf-8'))
    sig = hmac.new(secret.encode('utf-8'), payload_b64.encode('utf-8'), hashlib.sha256).digest()
    return payload_b64 + '.' + _b64url_encode(sig)


def _verify_token(token: str, secret: str) -> dict | None:
    try:
        payload_b64, sig_b64 = token.split('.', 1)
    except ValueError:
        return None
    expected = hmac.new(secret.encode('utf-8'), payload_b64.encode('utf-8'), hashlib.sha256).digest()
    try:
        got = _b64url_decode(sig_b64)
    except Exception:  # pylint: disable=broad-except
        return None
    if not hmac.compare_digest(expected, got):
        return None
    try:
        claims = json.loads(_b64url_decode(payload_b64).decode('utf-8'))
    except Exception:  # pylint: disable=broad-except
        return None
    now = int(datetime.now(tz=timezone.utc).timestamp())
    if int(claims.get('nbf', 0)) > now + 5:
        return None
    if int(claims.get('exp', 0)) < now:
        return None
    email = (claims.get('email') or '').strip().lower()
    if not email:
        return None
    return claims


@csrf_exempt
@require_GET
def lk_handoff(request):
    """
    GET /robbo/lk-handoff?token=...&next=http://localhost:3030/choose

    ЛК → Open edX: creates Django session for the user identified by email in the token.
    """
    secret = getattr(settings, 'ROBBO_LK_HANDOFF_SECRET', '') or ''
    if not secret:
        log.warning('robbo_lk_handoff: ROBBO_LK_HANDOFF_SECRET is empty')
        return HttpResponseForbidden('handoff disabled')

    token = (request.GET.get('token') or '').strip()
    next_url = (request.GET.get('next') or '').strip()
    if not token or not _allowed_next(next_url):
        return HttpResponseBadRequest('invalid token or next')

    claims = _verify_token(token, secret)
    if not claims:
        return HttpResponseForbidden('invalid or expired token')

    email = claims['email'].strip().lower()
    User = get_user_model()
    try:
        user = User.objects.get(email__iexact=email)
    except User.DoesNotExist:
        log.info('robbo_lk_handoff: no LMS user for email=%s', email)
        return HttpResponseForbidden('user not found')
    if not user.is_active:
        return HttpResponseForbidden('user inactive')

    # Backend auth already verified password in LK against LMS auth_user (or shared DB).
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    log.info('robbo_lk_handoff: session created for user_id=%s email=%s', user.id, email)
    return HttpResponseRedirect(next_url)


@login_required
@require_GET
def lk_portal(request):
    """
    GET /robbo/lk?next=http://localhost:3030/choose

    Open edX → ЛК: issues HMAC token and redirects to ЛК backend /auth/oidc/from-lms.
    Unauthenticated users are sent to LMS login (via @login_required), then back here.
    """
    secret = getattr(settings, 'ROBBO_LK_HANDOFF_SECRET', '') or ''
    if not secret:
        log.warning('robbo_lk_handoff: ROBBO_LK_HANDOFF_SECRET is empty')
        return HttpResponseForbidden('handoff disabled')

    backend_base = (getattr(settings, 'ROBBO_LK_BACKEND_BASE', '') or 'http://localhost:8080').rstrip('/')
    frontend_base = (getattr(settings, 'ROBBO_LK_FRONTEND_BASE', '') or 'http://localhost:3030').rstrip('/')

    next_url = (request.GET.get('next') or '').strip()
    if not next_url:
        next_url = frontend_base + '/choose'
    if not _allowed_next(next_url):
        return HttpResponseBadRequest('invalid next')

    email = (getattr(request.user, 'email', '') or '').strip().lower()
    if not email:
        return HttpResponseForbidden('user email missing')
    if not request.user.is_active:
        return HttpResponseForbidden('user inactive')

    token = _issue_token(email, secret)
    target = f'{backend_base}/auth/oidc/from-lms?{urlencode({"token": token, "next": next_url})}'
    log.info('robbo_lk_portal: redirecting user_id=%s to ЛК handoff', request.user.id)
    return HttpResponseRedirect(target)
