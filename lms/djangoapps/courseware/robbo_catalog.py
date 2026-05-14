# Copyright (C) 2024-2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of the Robbo Open edX distribution. See NOTICE at repository root.

# pylint: disable=missing-docstring
"""
Robbo /courses page: hero copy, featured course metadata, and catalog stubs.

All learner-visible strings for this page are defined here (single edit point);
templates only interpolate context. Later these can be replaced by a translation
layer without changing Mako/SCSS structure.

Image files live in the comprehensive theme at:
  themes/robbo-theme/lms/static/images/catalog/<filename>
Referenced in templates via staticfiles path ``images/catalog/...``.

Slug → source assets (replace files under ``images/catalog/`` when refreshing art):
  mcu.png               ← MCU illustration (featured + «микроконтроллеры» stub)
  stub-postgres.png     ← Photoroom export (591×320; legacy featured fallback)
  featured-mcu.png      ← carve.photos no-bg preview 552×320 (PostgreSQL stub card)
  stub-mcu-advanced.png ← legacy filename (replaced by mcu.png in data)
  stub-freecad.png      ← carve.photos no-bg preview 552×320
  stub-linux.png        ← carve.photos no-bg preview 552×320
  stub-manipulators.png ← carve.photos no-bg preview 552×320
  stub-ai.png           ← carve.photos no-bg preview 552×320
  stub-python.png       ← Photoroom export 552×320
  stub-industrial.png   ← carve.photos no-bg preview 552×320
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from django.conf import settings
from django.urls import reverse
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.models.course_details import CourseDetails
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
from openedx.core.djangolib.markup import HTML, Text

from common.djangoapps.student.models import CourseEnrollment


def get_robbo_courses_account_banners(request) -> Dict[str, Any]:
    """
    Page-top and featured-card notices for /courses (parity with learner dashboard patterns).

    - Anonymous: prompt to sign in / register (two placements: banner + featured line).
    - Authenticated, inactive: email activation copy (banner + «Требуется активация…» on card).
    """
    user = getattr(request, 'user', None)
    if user is None or (user.is_authenticated and user.is_active):
        return {
            'mode': 'none',
            'top_title': '',
            'top_body': None,
            'featured_line': '',
        }

    platform_name = configuration_helpers.get_value('platform_name', settings.PLATFORM_NAME)
    next_path = request.get_full_path() or '/courses'
    query = urlencode({'next': next_path})
    signin_url = f'{reverse("signin_user")}?{query}'
    register_url = f'{reverse("register_user")}?{query}'

    if not user.is_authenticated:
        top_body = Text(
            'Чтобы получить полный доступ к каталогу, {signin} или {register}.'
        ).format(
            signin=HTML(
                '<a class="robbo-courses-catalog__account-banner-link" href="{u}">войдите</a>'
            ).format(u=signin_url),
            register=HTML(
                '<a class="robbo-courses-catalog__account-banner-link" href="{u}">зарегистрируйтесь</a>'
            ).format(u=register_url),
        )
        return {
            'mode': 'anonymous',
            'top_title': 'Войдите или зарегистрируйтесь',
            'top_body': top_body,
            'featured_line': 'Для полного доступа к курсу войдите в учётную запись.',
        }

    activation_email_support_link = (
        configuration_helpers.get_value(
            'ACTIVATION_EMAIL_SUPPORT_LINK', settings.ACTIVATION_EMAIL_SUPPORT_LINK
        )
        or settings.SUPPORT_SITE_LINK
    )
    top_body = Text(
        'Проверьте почту {email_start}{email}{email_end} — мы отправили ссылку для активации '
        'учётной записи «{platform}». Если письма нет, загляните в «Спам» или '
        '{link_start}напишите в поддержку{link_end}.'
    ).format(
        email_start=HTML('<strong>'),
        email_end=HTML('</strong>'),
        email=user.email,
        platform=platform_name,
        link_start=HTML(
            '<a class="robbo-courses-catalog__account-banner-link" target="_blank" rel="noopener" '
            'href="{u}">'
        ).format(u=activation_email_support_link),
        link_end=HTML('</a>'),
    )
    return {
        'mode': 'inactive',
        'top_title': 'Активируйте свою учётную запись!',
        'top_body': top_body,
        'featured_line': 'Требуется активация для полного доступа',
    }


def get_robbo_catalog_hero() -> dict:
    return {
        'heading': 'Описание курсов',
        'lede': (
            'Каталог направлений: микроконтроллеры, СУБД, САПР, Linux, робототехника, ИИ, Python '
            'и промышленная автоматика.'
        ),
    }


def get_robbo_catalog_stubs() -> List[Dict[str, Any]]:
    """Eight placeholder courses: notify button is wired in JS to data-stub-id."""
    return [
        {
            'id': 'mcu-advanced',
            'title': 'Российские микроконтроллеры: продвинутый уровень',
            'description': (
                'Углублённое изучение архитектуры отечественных микросхем и создание сложных систем '
                'автоматизации на их основе. Мастерство разработки устройств с учётом специфики '
                'локальных компонентов.'
            ),
            'image': 'mcu.png',
            'notify_label': 'Сообщить об открытии',
        },
        {
            'id': 'postgres',
            'title': 'PostgreSQL: работа с базами данных',
            'description': (
                'Освоение принципов проектирования реляционных баз данных и написания сложных '
                'запросов для управления большими массивами информации. Практика администрирования и '
                'оптимизации производительности в среде PostgreSQL.'
            ),
            'image': 'featured-mcu.png',
            'notify_label': 'Сообщить об открытии',
        },
        {
            'id': 'freecad',
            'title': 'Проектирование в FreeCAD',
            'description': (
                'Изучение инструментов параметрического 3D-моделирования для создания точных '
                'инженерных деталей и сборных конструкций. Подготовка технической документации и '
                'моделей для производства в открытом ПО.'
            ),
            'image': 'stub-freecad.png',
            'notify_label': 'Сообщить об открытии',
        },
        {
            'id': 'linux-admin',
            'title': 'Системное администрирование Linux',
            'description': (
                'Настройка и поддержка серверных решений на базе ОС Linux, включая управление '
                'правами доступа и сетевую безопасность. Навыки работы в терминале и автоматизации '
                'задач для обеспечения стабильной ИТ-инфраструктуры.'
            ),
            'image': 'stub-linux.png',
            'notify_label': 'Сообщить об открытии',
        },
        {
            'id': 'manipulators',
            'title': 'Программирование промышленных манипуляторов',
            'description': (
                'Разработка алгоритмов движения и логики работы роботизированных рук для '
                'автоматизации производственных линий. Изучение интерфейсов взаимодействия и систем '
                'машинного зрения в робототехнике.'
            ),
            'image': 'stub-manipulators.png',
            'notify_label': 'Сообщить об открытии',
        },
        {
            'id': 'ai-production',
            'title': 'Применение ИИ в производственных процессах',
            'description': (
                'Внедрение нейросетей и алгоритмов анализа данных для прогнозирования износа '
                'оборудования и оптимизации выпуска продукции. Использование технологий машинного '
                'обучения для повышения эффективности предприятия.'
            ),
            'image': 'stub-ai.png',
            'notify_label': 'Сообщить об открытии',
        },
        {
            'id': 'python',
            'title': 'Программирование на Python',
            'description': (
                'Создание прикладного ПО и скриптов на одном из самых популярных языков мира для '
                'решения широкого спектра технических задач. От основ синтаксиса до разработки '
                'инструментов обработки данных и интеграции сервисов.'
            ),
            'image': 'stub-python.png',
            'notify_label': 'Сообщить об открытии',
        },
        {
            'id': 'industrial-controllers',
            'title': 'Отечественные промышленные контроллеры',
            'description': (
                'Изучение принципов работы и программирования локальных ПЛК для управления '
                'индустриальными объектами в рамках импортозамещения. Практические навыки создания '
                'надёжных систем промышленной автоматизации (АСУ ТП).'
            ),
            'image': 'stub-industrial.png',
            'notify_label': 'Сообщить об открытии',
        },
    ]


def _pick_featured_course(courses_list: list) -> Optional[Any]:
    """
    Use the first course in ``courses_list`` (same order as the view: sorted by start date or
    announcement). Optional ``ROBBO_CATALOG_FEATURED_COURSE_ID`` overrides when set and found.
    """
    if not courses_list:
        return None
    course_id = getattr(settings, 'ROBBO_CATALOG_FEATURED_COURSE_ID', None)
    if course_id:
        try:
            key = CourseKey.from_string(course_id)
        except InvalidKeyError:
            key = None
        if key is not None:
            for course in courses_list:
                if getattr(course, 'id', None) == key:
                    return course
            # Wrong id in settings: fall back to first available course in list.
    return courses_list[0]


def build_robbo_catalog_featured(
    request,
    courses_list: list,
) -> Optional[Dict[str, Any]]:
    """
    Build context for the featured (real) course: CTA points to MFE / LMS course home.
    """
    from openedx.features.course_experience import course_home_url  # pylint: disable=import-outside-toplevel

    course = _pick_featured_course(courses_list)
    if not course:
        return None

    image_filename = getattr(settings, 'ROBBO_CATALOG_FEATURED_IMAGE', 'mcu.png')
    title = course.display_name_with_default
    short = (getattr(course, 'short_description', None) or '').strip()
    if not short:
        short = get_course_excerpt_from_overview(course)
    if not short:
        short = (
            'Практический курс по российским микроконтроллерам: архитектура, локализация и '
            'портирование сценариев с открытой и проприетарной периферией.'
        )

    cta_url = course_home_url(course.id)
    if request and hasattr(request, 'build_absolute_uri') and cta_url.startswith('/'):
        cta_url = request.build_absolute_uri(cta_url)

    featured: Dict[str, Any] = {
        'course_id': str(course.id),
        'title': title,
        'description': short,
        'cta_url': cta_url,
        'cta_label': 'Начать обучение',
        'image': image_filename,
        'image_alt': title,
    }

    # Enroll-on-click: active users who are not yet enrolled POST to change_enrollment (see catalog JS).
    user = getattr(request, 'user', None) if request else None
    if user is not None and user.is_authenticated and user.is_active:
        if not CourseEnrollment.is_enrolled(user, course.id):
            featured['cta_enroll'] = True
            featured['change_enrollment_url'] = reverse('change_enrollment')

    return featured


def get_course_excerpt_from_overview(course) -> str:
    """Use overview HTML from CourseDetails if set."""
    try:
        key = course.id
        details = CourseDetails.fetch(key)
    except Exception:  # pylint: disable=broad-except
        return ''
    if not details or not details.overview:
        return ''
    return _html_to_snippet(str(details.overview), max_len=500)


def _html_to_snippet(html: str, max_len: int) -> str:
    import re  # pylint: disable=import-outside-toplevel
    from html import unescape  # pylint: disable=import-outside-toplevel

    text = re.sub(r'<[^>]+>', ' ', html)
    text = unescape(' '.join(text.split()))
    if len(text) > max_len:
        return text[: max_len - 1].rstrip() + '…'
    return text
