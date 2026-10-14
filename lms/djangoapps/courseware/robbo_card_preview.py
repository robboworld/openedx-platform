# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of the Robbo Open edX distribution. See NOTICE at repository root.

"""
Course card preview for the course team: the card as a new learner sees it in the /courses
catalog and in «Мои курсы» (learner dashboard MFE).

Studio (Schedule & Details, next to the card image) links to ``robbo_course_card_preview``;
the view checks access and redirects to the page with ``?robbo_card_preview=<course key>``.
That page renders a preview block on top — the real card markup for the course, even when it
is hidden from the catalog or the author is not enrolled — and leaves the rest unchanged.

Access: anyone who can edit the course in Studio (course team admin/staff, org staff, global
staff) and superusers. Limited staff has no Studio access and gets no preview.
"""
from __future__ import annotations

from typing import Any, Dict, Optional
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_GET
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey

from common.djangoapps.student.auth import has_studio_write_access
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview

CARD_PREVIEW_PARAM = 'robbo_card_preview'
CARD_PREVIEW_CATALOG = 'catalog'
CARD_PREVIEW_DASHBOARD = 'dashboard'


def user_can_preview_course_card(user, course_key) -> bool:
    """Course authors and above: whoever may edit the course in Studio."""
    if user is None or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return has_studio_write_access(user, course_key, service_variant='cms')


def get_card_preview_course_key(request) -> Optional[CourseKey]:
    """Course from ``?robbo_card_preview=`` when the current user may preview its card."""
    raw = (request.GET.get(CARD_PREVIEW_PARAM) or '').strip()
    if not raw:
        return None
    try:
        course_key = CourseKey.from_string(raw)
    except InvalidKeyError:
        return None
    if not user_can_preview_course_card(getattr(request, 'user', None), course_key):
        return None
    return course_key


def get_card_preview_overview(course_key) -> Optional[CourseOverview]:
    """``CourseOverview`` for the preview (built from the modulestore if missing)."""
    try:
        return CourseOverview.get_from_id(course_key)
    except CourseOverview.DoesNotExist:
        return None


def get_card_preview_url(course_key, target: str) -> Optional[str]:
    """Absolute URL of the catalog or «Мои курсы» with the preview parameter."""
    query = urlencode({CARD_PREVIEW_PARAM: str(course_key)})
    if target == CARD_PREVIEW_CATALOG:
        return f'{settings.LMS_ROOT_URL.rstrip("/")}{reverse("courses")}?{query}'
    if target == CARD_PREVIEW_DASHBOARD:
        learner_home = getattr(settings, 'LEARNER_HOME_MICROFRONTEND_URL', None)
        if learner_home:
            return f'{learner_home.rstrip("/")}/?{query}'
    return None


def get_card_preview_studio_url(course_key) -> str:
    """Schedule & Details in Studio, where the card image and description are edited."""
    from lms.djangoapps.courseware.robbo_catalog import get_robbo_studio_root_url  # pylint: disable=import-outside-toplevel

    studio_root = get_robbo_studio_root_url()
    if not studio_root:
        return ''
    return f'{studio_root}/settings/details/{course_key}'


@login_required
@require_GET
def course_card_preview(request, course_id, target):
    """Studio entry point: check access and open the catalog or «Мои курсы» in preview mode."""
    try:
        course_key = CourseKey.from_string(course_id)
    except InvalidKeyError as exc:
        raise Http404 from exc
    if not user_can_preview_course_card(request.user, course_key):
        raise PermissionDenied
    url = get_card_preview_url(course_key, target)
    if not url:
        raise Http404
    return redirect(url)


def build_catalog_card_preview(request, catalog_courses: list) -> Optional[Dict[str, Any]]:
    """
    Preview block for /courses, or None without an allowed ``?robbo_card_preview=``.

    ``catalog_courses`` is the learner catalog list: it tells whether learners see the course now.
    """
    from lms.djangoapps.courseware.robbo_catalog import build_robbo_catalog_course_cards  # pylint: disable=import-outside-toplevel

    course_key = get_card_preview_course_key(request)
    if course_key is None:
        return None
    overview = get_card_preview_overview(course_key)
    if overview is None:
        return None

    card = build_robbo_catalog_course_cards(request, [overview], as_new_learner=True)[0]
    in_catalog = any(course.id == course_key for course in catalog_courses)
    if in_catalog:
        text = (
            'Так курс выглядит в каталоге для слушателей, которые ещё не записаны. '
            'Здесь карточка стоит первой, а в каталоге — на своём месте среди других курсов.'
        )
    else:
        text = (
            'Сейчас курса нет в каталоге, поэтому слушатели эту карточку не видят. '
            'Так она будет выглядеть, когда курс появится в каталоге.'
        )

    return {
        'card': card,
        'eyebrow': 'Предпросмотр',
        'title': 'Карточка курса в каталоге',
        'text': text,
        'is_hidden': not in_catalog,
        'hidden_label': 'Курса нет в каталоге',
        'note': 'Этот блок видите только вы.',
        'dashboard_url': get_card_preview_url(course_key, CARD_PREVIEW_DASHBOARD),
        'dashboard_label': 'Посмотреть в «Моих курсах»',
        'studio_url': get_card_preview_studio_url(course_key),
        'studio_label': 'Вернуться в редактор курсов',
        'exit_url': reverse('courses'),
        'exit_label': 'Закрыть предпросмотр',
    }
