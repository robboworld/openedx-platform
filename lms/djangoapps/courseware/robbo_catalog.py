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

from common.djangoapps.student.models import CourseAccessRole, CourseEnrollment
from common.djangoapps.student.roles import (
    CourseInstructorRole,
    CourseLimitedStaffRole,
    CourseStaffRole,
    GlobalStaff,
)

# Course team in Studio + platform personnel (see instructor-catalog tooltip).
_INSTRUCTOR_CATALOG_ROLE_NAMES = frozenset({
    CourseStaffRole.ROLE,
    CourseLimitedStaffRole.ROLE,
    CourseInstructorRole.ROLE,
})


def user_can_see_robbo_instructor_catalog(user) -> bool:
    """
    True for course team, platform superuser, or platform staff (see tooltip on /courses).
    """
    if user is None or not user.is_authenticated:
        return False
    if getattr(user, 'is_superuser', False):
        return True
    if GlobalStaff().has_user(user):
        return True
    return CourseAccessRole.objects.filter(
        user=user,
        role__in=_INSTRUCTOR_CATALOG_ROLE_NAMES,
    ).exists()


def get_robbo_instructor_catalog_banner(course_count: int = 0) -> Dict[str, Any]:
    """
    Copy for the instructor-only section divider on /courses.

    See docs/design/robbo-courses-catalog-instructor-banner.md for layout spec.
    """
    label = 'Ниже расположены курсы, которые видят только преподаватели'
    label_html = Text('Ниже расположены курсы, которые видят только {accent}').format(
        accent=_build_instructor_tip_accent_html(),
    )
    return {
        'label': label,
        'label_html': label_html,
    }


def _build_instructor_tip_accent_html() -> HTML:
    """«преподаватели» with hover/focus tooltip listing Studio course-team roles."""
    return HTML(
        '<div class="robbo-courses-catalog__instructor-tip">'
        '<span class="robbo-courses-catalog__instructor-tip-anchor" '
        'tabindex="0" role="button" '
        'aria-label="Подсказка: кто считается преподавателем" '
        'aria-describedby="robbo-instructor-role-tip">'
        '<span class="robbo-courses-catalog__instructor-bar-accent">преподаватели</span>'
        '<span class="robbo-courses-catalog__instructor-tip-icon" aria-hidden="true">'
        '<svg class="robbo-courses-catalog__instructor-tip-icon-svg" width="14" height="14" '
        'viewBox="0 0 16 16" focusable="false" xmlns="http://www.w3.org/2000/svg">'
        '<circle cx="8" cy="8" r="7" stroke="currentColor" stroke-width="1.5" fill="none"/>'
        '<path d="M8 7.1V11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>'
        '<circle cx="8" cy="4.9" r="0.9" fill="currentColor"/>'
        '</svg>'
        '</span>'
        '</span>'
        '<div id="robbo-instructor-role-tip" role="tooltip" '
        'class="robbo-courses-catalog__instructor-tip-popup">'
        '<p class="robbo-courses-catalog__instructor-tip-heading">'
        'Кто считается преподавателем'
        '</p>'
        '<ul class="robbo-courses-catalog__instructor-tip-list">'
        '<li>Главный инструктор курса</li>'
        '<li>Член команды курса</li>'
        '<li>Администратор</li>'
        '<li>Персонал образовательной платформы</li>'
        '</ul>'
        '</div>'
        '</div>'
    )


def get_robbo_instructor_catalog_courses(public_courses_list: list) -> List[Any]:
    """
    All published site courses hidden from the learner catalog (any ``catalog_visibility``).

    ``CourseOverview`` only includes published runs. Courses already shown in the public
    grid above are excluded to avoid duplicate cards.
    """
    from lms.djangoapps.branding import get_visible_courses  # pylint: disable=import-outside-toplevel

    public_ids = {course.id for course in public_courses_list}
    return [course for course in get_visible_courses() if course.id not in public_ids]


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
    """Empty hero shell on /courses (intro copy lives in the about block below)."""
    return {
        'heading': '',
        'lede': '',
    }


def get_robbo_catalog_about() -> Dict[str, Any]:
    """«О компании» block in guest homepage hero (right column)."""
    return {
        'title': 'О компании',
        'tagline': 'Открытые технологии будущего',
        'stats': [
            {'value': '19', 'label': 'лет на рынке'},
            {'value': '44', 'label': 'стран мира'},
        ],
        'intro': (
            'Уже 19 лет мы внедряем технологии на базе открытого кода (Open Source), развиваем '
            'робототехнику и занимаемся системной интеграцией сложных инженерных систем. Наши '
            'продукты и методики востребованы в '
        ),
        'intro_accent': '44 странах мира',
        'highlights': [
            {
                'label': 'Институты развития:',
                'text': 'лидерский проект АСИ, Лидер НТИ, резидент «Сколково» и кластера «Ломоносов».',
            },
            {
                'label': 'При поддержке:',
                'text': 'Минпромторг, Минцифры, Минобрнауки, Минэкономразвития.',
            },
        ],
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


def _absolute_url(request, path: str) -> str:
    if request and hasattr(request, 'build_absolute_uri') and path.startswith('/'):
        return request.build_absolute_uri(path)
    return path


def _catalog_course_image_url(course) -> str:
    """Thumbnail for catalog cards; ``get_courses`` returns ``CourseOverview`` instances."""
    image_urls = getattr(course, 'image_urls', None)
    if image_urls:
        return (
            image_urls.get('small')
            or image_urls.get('large')
            or image_urls.get('raw')
            or ''
        )
    return getattr(course, 'course_image_url', '') or (
        settings.STATIC_URL + settings.DEFAULT_COURSE_ABOUT_IMAGE_URL
    )



def _catalog_course_uses_placeholder_image(course) -> bool:
    """True when the card will show the platform default / missing-course artwork."""
    raw = (_catalog_course_image_url(course) or '').strip()
    if not raw:
        return True

    path = raw.split('?', 1)[0].rstrip('/')
    if path.endswith('no_course_image.png'):
        return True

    default = (settings.STATIC_URL + settings.DEFAULT_COURSE_ABOUT_IMAGE_URL).rstrip('/')
    return path == default or path.endswith(default.lstrip('/'))


def build_robbo_catalog_course_cards(
    request,
    courses_list: list,
) -> List[Dict[str, Any]]:
    """
    Catalog grid cards for courses visible on /courses (same list as ``get_courses`` in the view).
    """
    from openedx.features.course_experience import course_home_url  # pylint: disable=import-outside-toplevel

    cards: List[Dict[str, Any]] = []
    user = getattr(request, 'user', None) if request else None

    for course in courses_list:
        title = course.display_name_with_default
        short = (getattr(course, 'short_description', None) or '').strip()
        if not short:
            short = get_course_excerpt_from_overview(course)
        short = _normalize_catalog_course_description(short)

        cta_url = _absolute_url(request, course_home_url(course.id))
        image_url = _absolute_url(request, _catalog_course_image_url(course))
        about_url = _absolute_url(request, reverse('about_course', args=[str(course.id)]))
        is_image_placeholder = _catalog_course_uses_placeholder_image(course)

        card: Dict[str, Any] = {
            'course_id': str(course.id),
            'title': title,
            'description': short,
            'image_url': image_url,
            'image_alt': title,
            'is_image_placeholder': is_image_placeholder,
            'about_url': about_url,
            'cta_url': cta_url,
            'cta_label': 'Начать обучение',
        }
        card.update(_course_card_meta(course))

        if user is not None and user.is_authenticated and user.is_active:
            if CourseEnrollment.is_enrolled(user, course.id):
                card['is_enrolled'] = True
                card['cta_label'] = 'Продолжить обучение'
                progress_percent = _enrolled_course_progress_percent(user, course.id)
                if progress_percent is not None and progress_percent > 0:
                    card['progress_percent'] = progress_percent
            else:
                card['cta_enroll'] = True
                card['change_enrollment_url'] = reverse('change_enrollment')

        cards.append(card)

    return cards


def _guest_course_price_offer(course) -> Dict[str, Any]:
    """Price badge and register CTA copy for guest landing cards."""
    from common.djangoapps.course_modes.models import CourseMode  # pylint: disable=import-outside-toplevel
    from lms.djangoapps.robbo_payments.utils import format_checkout_price_display  # pylint: disable=import-outside-toplevel

    verified = CourseMode.verified_mode_for_course(course.id)
    if verified and int(verified.min_price) > 0:
        price_display = format_checkout_price_display(verified.min_price, verified.currency)
        return {
            'cta_label': f'Записаться — {price_display}',
        }
    return {
        'cta_label': 'Записаться бесплатно',
    }


def _guest_course_register_cta(request, course, about_path: str) -> Dict[str, Any]:
    """Per-course registration URL (next = course about page) for anonymous guests."""
    offer = _guest_course_price_offer(course)
    next_url = _absolute_url(request, about_path)
    register_path = reverse('register_user') + '?' + urlencode({'next': next_url})
    return {
        'cta_url': _absolute_url(request, register_path),
        'cta_label': offer['cta_label'],
        'show_about_link': True,
    }


def build_robbo_guest_homepage_course_cards(
    request,
    courses_list: list,
) -> List[Dict[str, Any]]:
    """
    Guest landing (/) course cards: register CTA per course (next = about page).
    """
    from openedx.features.course_experience import course_home_url  # pylint: disable=import-outside-toplevel

    cards: List[Dict[str, Any]] = []
    user = getattr(request, 'user', None) if request else None
    is_authenticated = user is not None and user.is_authenticated

    for course in courses_list:
        title = course.display_name_with_default
        short = (getattr(course, 'short_description', None) or '').strip()
        if not short:
            short = get_course_excerpt_from_overview(course)
        short = _normalize_guest_course_description(short)

        about_path = reverse('about_course', args=[str(course.id)])
        about_url = _absolute_url(request, about_path)
        image_url = _absolute_url(request, _catalog_course_image_url(course))

        card: Dict[str, Any] = {
            'course_id': str(course.id),
            'title': title,
            'description': short,
            'image_url': image_url,
            'image_alt': title,
            'is_image_placeholder': _catalog_course_uses_placeholder_image(course),
            'about_url': about_url,
        }
        card.update(_course_card_meta(course))
        card['teaser'] = _guest_card_teaser(short)

        if is_authenticated:
            card.update({
                'cta_url': _absolute_url(request, course_home_url(course.id)),
                'cta_label': 'Начать обучение',
                'show_about_link': False,
            })
        else:
            card.update(_guest_course_register_cta(request, course, about_path))

        cards.append(card)

    return cards


def _guest_card_teaser(text: str, max_len: int = 96) -> str:
    """One-line teaser for compact landing cards."""
    snippet = _normalize_guest_course_description(text)
    if not snippet:
        return ''
    if len(snippet) > max_len:
        return snippet[: max_len - 1].rstrip() + '…'
    return snippet


_GUEST_COURSE_DESC_BOILERPLATE = (
    'about this course',
    'include your long course description here',
    'include your course description here',
    'enter short description',
)

# Default Open edX overview / short_description placeholder (catalog cards).
_CATALOG_DEFAULT_DESC_PREFIX = 'about this course include your long course'


def _normalize_catalog_course_description(text: str) -> str:
    """Drop Open edX placeholder copy from catalog and guest landing cards."""
    snippet = (text or '').strip()
    if not snippet:
        return ''
    lowered = snippet.lower()
    if lowered.startswith(_CATALOG_DEFAULT_DESC_PREFIX):
        return ''
    for phrase in _GUEST_COURSE_DESC_BOILERPLATE:
        if phrase in lowered:
            return ''
    return snippet


def _normalize_guest_course_description(text: str) -> str:
    """Drop Open edX placeholder copy from guest landing cards."""
    return _normalize_catalog_course_description(text)


def _course_card_meta(course) -> Dict[str, str]:
    """Start date for catalog and guest landing cards (single-line meta row)."""
    meta: Dict[str, str] = {}

    advertised_start = getattr(course, 'advertised_start', None)
    if advertised_start:
        meta['start_label'] = f'Старт: {advertised_start}'
    else:
        start = getattr(course, 'start', None)
        if start is not None:
            meta['start_label'] = f'Старт: {start.strftime("%d.%m.%Y")}'

    return meta


def _enrolled_course_progress_percent(user, course_key) -> Optional[int]:
    """Unit completion percent for enrolled learners; None if unavailable or no countable units."""
    try:
        from lms.djangoapps.courseware.courses import get_course_blocks_completion_summary  # pylint: disable=import-outside-toplevel

        summary = get_course_blocks_completion_summary(course_key, user)
    except Exception:  # pylint: disable=broad-except
        return None

    complete = int(summary.get('complete_count') or 0)
    incomplete = int(summary.get('incomplete_count') or 0)
    total = complete + incomplete
    if total <= 0:
        return None

    return min(100, max(0, round(100 * complete / total)))


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
    short = _normalize_catalog_course_description(short)
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
