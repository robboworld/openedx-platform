# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (certificate designs). See NOTICE at repository root.
"""
Certificate readiness checks for the LMS instructor dashboard («Сертификаты» tab).

* ``tab_conditions`` — why the tab is (un)available: the stock rules of
  ``instructor_dashboard_2`` (platform switch, not a CCX, who may manage certificates).
* ``course_checks`` — whether the course is set up to issue certificates: the course has the
  «honor» mode and no active enrollment is «audit» (both fixable with one button by platform
  staff, see views.py; paid «verified» enrollments are left alone), web certificate on and active in Studio,
  chosen design, the course has started, certificates are available before the course ends (warning only).

Titles describe the current state («Сертификат выдаётся…» / «Сертификат не выдаётся…»), not the requirement.
Each check: {"key", "status": ok | fail | warn | info | note (special info, shown first), "title", "detail", "link", "link_label",
"action": None | {"url", "label", "confirm"}, "admin_only": bool}.
Superusers also get the names of platform-level settings and links to them; checks with ``admin_only``
are shown to superusers only (marked «Видит только администратор»).
User-facing text is Russian (see .cursor/rules/user-facing-copy-ru.mdc).
"""

from collections import defaultdict
from datetime import datetime, timezone

from django.conf import settings

from django.db.models import Count
from django.urls import reverse

from common.djangoapps.course_modes.models import CourseMode
from common.djangoapps.student.models import CourseEnrollment
from lms.djangoapps.certificates import api as certs_api
from lms.djangoapps.certificates.models import CertificateGenerationConfiguration, CertificateGenerationCourseSetting
from xmodule.data import CertificatesDisplayBehaviors
from xmodule.modulestore import ModuleStoreEnum
from xmodule.modulestore.django import modulestore

from .designs import DESIGN_OVERRIDE_KEY, get_design

OK, FAIL, WARN, INFO, NOTE = 'ok', 'fail', 'warn', 'info', 'note'

def _check(key, status, title, detail='', link=None, link_label=None, action=None, admin_only=False):
    return {
        'key': key, 'status': status, 'title': title, 'detail': detail,
        'link': link, 'link_label': link_label, 'action': action, 'admin_only': admin_only,
    }


def can_fix_course(user):
    """One-click fixes (course mode, enrollment modes) are for platform staff and superusers only."""
    return bool(user.is_staff or user.is_superuser)


def enrollments_by_mode(course_key):
    """{mode: count} of active enrollments."""
    rows = (
        CourseEnrollment.objects.filter(course_id=course_key, is_active=True)
        .values('mode').annotate(count=Count('id')).order_by('mode')
    )
    return {row['mode']: row['count'] for row in rows}


def studio_certificates_url(course_key):
    authoring = (getattr(settings, 'MFE_CONFIG', None) or {}).get('COURSE_AUTHORING_MICROFRONTEND_URL')
    if authoring:
        return f'{authoring.rstrip("/")}/course/{course_key}/certificates'
    return f'//{settings.CMS_BASE}/certificates/{course_key}'


def studio_schedule_url(course_key):
    authoring = (getattr(settings, 'MFE_CONFIG', None) or {}).get('COURSE_AUTHORING_MICROFRONTEND_URL')
    if authoring:
        return f'{authoring.rstrip("/")}/course/{course_key}/settings/details'
    return f'//{settings.CMS_BASE}/settings/details/{course_key}'


# Studio shows the upstream default assignment types in Russian
# (frontend-app-authoring src/grading-settings/localizeDefaultGradingLabels.js)
_GRADER_LABELS = {
    'Homework': 'Домашнее задание',
    'Lab': 'Лабораторная работа',
    'Midterm Exam': 'Промежуточный экзамен',
    'Final Exam': 'Итоговый экзамен',
}


# How a subsection gets its assignment type in Studio (Russian UI of frontend-app-authoring)
GRADING_HINT = (
    'Тип задания из «Оценивания» нужно назначить соответствующему подразделу: «Структура курса» → '
    'у подраздела «Настроить» → «Оценка» → «Оценка как:» — выберите тип. Число подразделов каждого типа '
    'должно совпадать с количеством в «Оценивании».'
)


def _grader_label(assignment_type):
    return _GRADER_LABELS.get(assignment_type, assignment_type)


def studio_grading_url(course_key):
    authoring = (getattr(settings, 'MFE_CONFIG', None) or {}).get('COURSE_AUTHORING_MICROFRONTEND_URL')
    if authoring:
        return f'{authoring.rstrip("/")}/course/{course_key}/settings/grading'
    return f'//{settings.CMS_BASE}/settings/grading/{course_key}'


def grading_problems(course_key):
    """
    The warnings of Studio «Оценивание» (grading settings) page, plus subsections of a type that is not
    in the grading policy. Counted on the draft branch, like Studio
    (cms contentstore.utils.get_subsections_by_assignment_type).

    Returns (problems: [str], usage: {type: count}, graders: [type]).
    """
    store = modulestore()
    usage = defaultdict(int)
    with store.branch_setting(ModuleStoreEnum.Branch.draft_preferred, course_key):
        course = store.get_course(course_key, depth=2)
        graders = list(course.raw_grader or [])
        for section in course.get_children():
            for subsection in section.get_children():
                if subsection.format:
                    usage[subsection.format] += 1

    problems = []
    if not graders:
        problems.append('В настройках оценивания нет ни одного типа заданий — ученик не сможет набрать проходной балл.')
    for grader in graders:
        assignment_type = grader.get('type', '')
        expected = int(grader.get('min_count') or 0)
        found = usage.get(assignment_type, 0)
        if not found:
            problems.append(
                f'«{_grader_label(assignment_type)}»: в курсе нет заданий этого типа (в настройках — {expected}).'
            )
        elif found != expected:
            problems.append(f'«{_grader_label(assignment_type)}»: в настройках {expected}, в курсе {found}.')
    known = {grader.get('type') for grader in graders}
    for assignment_type, found in sorted(usage.items()):
        if assignment_type not in known:
            problems.append(
                f'«{_grader_label(assignment_type)}»: этот тип назначен подразделам ({found}), '
                'но его нет в настройках оценивания.'
            )
    return problems, dict(usage), [grader.get('type') for grader in graders]


# Koa value removed by Open edX in 2021 (lms/djangoapps/certificates/docs/decisions/005-cert-display-settings.rst):
# it showed the certificate before the course end; the platform now reads it as «end».
LEGACY_EARLY_WITH_INFO = 'early_with_info'


def display_behavior_repair_value(stored):
    """
    None when the stored certificates_display_behavior is fine; otherwise the value to write instead:
    the intended value for 'CertificatesDisplayBehaviors.X' strings, «early_no_info» for the Koa «early_with_info»
    (keeps «available before the course end»), «end» (what the platform assumes) for unknown ones.
    """
    if stored is None or isinstance(stored, CertificatesDisplayBehaviors):
        return None
    if stored == LEGACY_EARLY_WITH_INFO:
        return CertificatesDisplayBehaviors.EARLY_NO_INFO.value
    normalized = CertificatesDisplayBehaviors.normalize(stored)
    if normalized == stored and CertificatesDisplayBehaviors.includes_value(stored):
        return None
    if CertificatesDisplayBehaviors.includes_value(normalized):
        return normalized
    return CertificatesDisplayBehaviors.END.value


def tab_conditions(course_key, access, instructor_manage_enabled, is_superuser=False):
    """
    Conditions of the stock dashboard for showing the certificates tab.

    Only superusers (platform administrators) use Django admin; everyone else, global staff included,
    is told to ask the administrator.
    """
    platform_enabled = CertificateGenerationConfiguration.current().enabled
    can_manage = access['admin'] or (access['instructor'] and instructor_manage_enabled)
    ask_admin = 'Чтобы получить доступ, обратитесь к администратору платформы.'
    if access['admin']:
        manage_detail = 'Вы сотрудник платформы.'
    elif instructor_manage_enabled:
        manage_detail = (
            'Вы главный инструктор курса.' if access['instructor']
            else f'Управлять сертификатами могут главный инструктор курса и сотрудники платформы. {ask_admin}'
        )
    else:
        manage_detail = f'Управлять сертификатами могут только сотрудники платформы. {ask_admin}'

    if platform_enabled:
        platform_detail, platform_link, platform_link_label = 'Одна настройка на всю платформу.', None, None
    elif is_superuser:
        platform_detail = (
            'Включите его в админке: «Certificates» → «Certificate generation configurations» '
            '→ новая запись с отметкой «Enabled». Настройка одна на всю платформу: она открывает эту вкладку '
            '(повторная выдача, исключения, аннулирование) и позволяет разрешить ученикам запрашивать сертификат.'
        )
        platform_link = '/admin/certificates/certificategenerationconfiguration/'
        platform_link_label = 'Открыть админку'
    else:
        platform_detail = (
            'Обратитесь к администратору платформы, чтобы он включил управление сертификатами. '
            'Без него не работают эта вкладка (повторная выдача, исключения, аннулирование) '
            'и запрос сертификата учениками.'
        )
        platform_link = platform_link_label = None

    conditions = [
        _check(
            'platform', OK if platform_enabled else FAIL,
            'Управление сертификатами включено на платформе' if platform_enabled
            else 'Управление сертификатами выключено на платформе',
            platform_detail, platform_link, platform_link_label,
        ),
        _check(
            'access', OK if can_manage else FAIL,
            'Есть права на управление сертификатами' if can_manage else 'Нет прав на управление сертификатами',
            manage_detail,
        ),
    ]
    if hasattr(course_key, 'ccx'):
        conditions.append(_check(
            'ccx', FAIL, 'Курс — копия CCX',
            'В CCX-курсах сертификаты настраиваются в исходном курсе.',
        ))
    return conditions


def course_checks(course, can_fix=False, is_superuser=False):
    """Is the course set up to issue certificates. «Сведения» (info) items always go last."""
    course_key = course.id
    studio_url = studio_certificates_url(course_key)
    checks = []

    # Platform-wide waffle switch: without it nobody gets a certificate for passing the course.
    # A special note («Важно знать», NOTE) for all course staff, first in the grid: with the switch on the
    # «Разрешить обучающимся выпускать себе сертификаты» button below is not needed. Superusers, who can change
    # the switch, get its name and a link to it.
    auto_enabled = certs_api.auto_certificate_generation_enabled()
    if auto_enabled:
        auto_title = 'Сертификат выдаётся автоматически при сдаче курса'
        auto_detail = (
            'На платформе включён переключатель «certificates.auto_certificate_generation»: ученик получает '
            'сертификат сам, как только наберёт проходной балл. Поэтому нажимать «Разрешить обучающимся '
            'выпускать себе сертификаты» не нужно — эта кнопка только добавляет ученикам «Запросить сертификат» '
            'на странице «Прогресс».' if is_superuser else
            'Ученик получает сертификат сам, как только наберёт проходной балл. Разрешать ученикам выпускать '
            'сертификаты (кнопка ниже на этой вкладке) не нужно.'
        )
    else:
        auto_title = 'Сертификат не выдаётся автоматически при сдаче курса'
        auto_detail = (
            'Ученик, сдавший курс, сам сертификат не получает. Включите переключатель '
            '«certificates.auto_certificate_generation» в админке: «Django-Waffle» → «Switches» '
            '(отметка «Active»). Он один на всю платформу.' if is_superuser else
            'Ученик, сдавший курс, получит сертификат, только если разрешить ученикам выпускать сертификаты '
            'на этой вкладке или выпустить сертификаты вручную. Автоматическую выдачу включает '
            'администратор платформы.'
        )
    show_switch_link = is_superuser and not auto_enabled
    checks.append(_check(
        'auto', NOTE, auto_title, auto_detail,
        '/admin/waffle/switch/' if show_switch_link else None,
        'Открыть переключатели' if show_switch_link else None,
    ))

    modes = list(CourseMode.objects.filter(course_id=course_key).values_list('mode_slug', flat=True))
    has_honor = CourseMode.HONOR in modes
    # «audit» next to «honor»: the course page enrolls in «honor», Learning MFE in «audit» (no certificate)
    audit_with_honor = has_honor and CourseMode.AUDIT in modes
    others = [slug for slug in modes if slug != CourseMode.HONOR]
    if not has_honor:
        honor_status = FAIL
        honor_title = 'У курса нет режима записи «honor»'
        honor_detail = (
            'Сертификаты выдаются ученикам в режиме «honor», а у курса его нет'
            + (f' (сейчас: {", ".join(modes)}).' if modes else '.')
        )
        honor_action = {
            'url': reverse('robbo_certificates:add_honor_mode', kwargs={'course_id': str(course_key)}),
            'label': 'Добавить режим «honor»',
            'confirm': 'Добавить курсу бесплатный режим записи «honor»?',
        }
    elif audit_with_honor:
        honor_status = WARN
        honor_title = 'У курса два бесплатных режима: «honor» и «audit»'
        honor_detail = (
            'Со страницы курса ученик запишется в «honor», '
            'а кнопкой «Записаться» внутри курса — в «audit» и сертификат не получит. '
            'Для бесплатного курса с сертификатом «audit» не нужен.'
        )
        honor_action = {
            'url': reverse('robbo_certificates:remove_audit_mode', kwargs={'course_id': str(course_key)}),
            'label': 'Убрать режим «audit»',
            'confirm': (
                'Убрать у курса режим «audit»? Новые ученики будут записываться в «honor». '
                'Уже записанных в «audit» это не изменит — для них есть отдельная кнопка.'
            ),
        }
    else:
        honor_status = OK
        honor_title = 'У курса есть режим записи «honor»'
        honor_detail = f'Другие режимы курса: {", ".join(others)}.' if others else 'Других режимов нет.'
        honor_action = None
    checks.append(_check(
        'honor_mode', honor_status, honor_title, honor_detail,
        action=honor_action if can_fix else None,
    ))

    by_mode = enrollments_by_mode(course_key)
    audit_count = by_mode.get(CourseMode.AUDIT, 0)
    others = ', '.join(f'{mode}: {count}' for mode, count in by_mode.items() if mode != CourseMode.AUDIT)
    checks.append(_check(
        'enrollments', FAIL if audit_count else OK,
        f'Есть ученики в режиме «audit»: {audit_count}' if audit_count else 'Нет учеников в режиме «audit»',
        ('Этот режим сертификат не даёт. ' if audit_count else '')
        + (f'Остальные записи: {others}.' if others else 'Других записей нет.'),
        action=None if not audit_count or not can_fix or not has_honor else {
            'url': reverse('robbo_certificates:enrollments_to_honor', kwargs={'course_id': str(course_key)}),
            'label': f'Перевести «audit» в «honor» ({audit_count})',
            'confirm': f'Перевести {audit_count} учеников из «audit» в «honor»? Платные записи не изменятся.',
        },
    ))

    html_enabled = settings.FEATURES.get('CERTIFICATES_HTML_VIEW', False) and course.cert_html_view_enabled
    checks.append(_check(
        'html', OK if html_enabled else FAIL,
        'Сертификат открывается как веб-страница' if html_enabled else 'Сертификат не открывается как веб-страница',
        '' if html_enabled else 'В дополнительных настройках курса включите «Certificate Web/HTML View Enabled».',
        None if html_enabled else studio_url,
        None if html_enabled else 'Открыть редактор курса',
    ))

    active = certs_api.get_active_web_certificate(course)
    created = bool((course.certificates or {}).get('certificates'))
    if active:
        active_title = 'Сертификат создан и активирован в редакторе курса'
        active_detail = f'Активный сертификат: «{active.get("name") or "без названия"}».'
    elif created:
        active_title = 'Сертификат создан, но не активирован'
        active_detail = 'На странице «Сертификаты» в редакторе курса нажмите «Активировать».'
    else:
        active_title = 'Сертификат не создан в редакторе курса'
        active_detail = 'На странице «Сертификаты» в редакторе курса создайте сертификат и нажмите «Активировать».'
    checks.append(_check(
        'active', OK if active else FAIL,
        active_title, active_detail,
        studio_url, 'Открыть сертификаты курса',
    ))

    # Studio «Оценивание»: assignment counts must match the grading policy, otherwise grades are off
    problems, usage, grader_types = grading_problems(course_key)
    checks.append(_check(
        'grading', FAIL if problems else OK,
        'Задания курса не совпадают с настройками оценивания' if problems
        else 'Задания курса совпадают с настройками оценивания',
        '\n'.join(problems + [GRADING_HINT]) if problems else ', '.join(
            f'«{_grader_label(assignment_type)}»: {usage.get(assignment_type, 0)}'
            for assignment_type in grader_types
        ) + '.',
        studio_grading_url(course_key), 'Открыть оценивание',
    ))

    design = get_design((course.cert_html_view_overrides or {}).get(DESIGN_OVERRIDE_KEY))
    checks.append(_check(
        'design', INFO, f'Оформление сертификата: «{design["title"]}»',
        'Меняется на странице «Сертификаты» в редакторе курса.',
        studio_url, 'Выбрать оформление',
    ))

    schedule_url = studio_schedule_url(course_key)
    start = course.start
    started = start is None or start <= datetime.now(timezone.utc)
    checks.append(_check(
        'start', OK if started else FAIL,
        'Курс уже начался' if started else 'Курс ещё не начался',
        f'Дата начала: {start:%d.%m.%Y}.' if start and started else (
            f'Курс начнётся {start:%d.%m.%Y} — до этой даты сертификаты не выдаются.' if start
            else 'Дата начала не задана.'
        ),
        None if started else schedule_url, None if started else 'Изменить дату начала',
    ))

    # A display behavior stored as 'CertificatesDisplayBehaviors.X' (Studio bug on Python 3.11, see
    # CertificatesDisplayBehaviors.normalize) or an unknown value: the platform falls back to «after the course end».
    stored_behavior = course.certificates_display_behavior
    repaired_behavior = display_behavior_repair_value(stored_behavior)
    if repaired_behavior is not None:
        if stored_behavior == LEGACY_EARLY_WITH_INFO:
            invalid_detail = (
                'В настройках курса осталось значение «early_with_info» из Koa: платформа его больше не знает и '
                'показывает сертификат только после окончания курса. На Koa он был доступен раньше — '
                f'этому соответствует «{repaired_behavior}» («Сразу после прохождения»). '
            )
        else:
            invalid_detail = (
                f'В настройках курса записано «{stored_behavior}» вместо «{repaired_behavior}». '
                'Из-за этого ученики могут не увидеть сертификат до окончания курса. '
            )
        invalid_detail += (
            'Кнопка ниже исправит запись.' if can_fix
            else 'Обратитесь к администратору платформы, чтобы он исправил запись.'
        )
        checks.append(_check(
            'display_invalid', FAIL, 'Значение показа сертификата записано с ошибкой', invalid_detail,
            action=None if not can_fix else {
                'url': reverse('robbo_certificates:repair_display_behavior', kwargs={'course_id': str(course_key)}),
                'label': 'Исправить значение',
                'confirm': f'Записать в настройки курса «{repaired_behavior}» вместо «{stored_behavior}»?',
            },
        ))

    # Studio: «Расписание и подробности» → «Поведение сертификата при отображении» should be «Сразу после прохождения»
    # (warning otherwise). Studio shows the field only for instructor-paced courses with auto generation on
    # (certs_api.can_show_certificate_available_date_field), yet the stored value always applies.
    # The certificate is generated on passing either way; the setting only decides when the learner can open it.
    behavior = CertificatesDisplayBehaviors.normalize(course.certificates_display_behavior)
    early = course.self_paced or behavior == CertificatesDisplayBehaviors.EARLY_NO_INFO.value
    if early:
        early_title = 'Сертификат доступен сразу после прохождения курса'
        early_detail = (
            'Курс в своём темпе: ученик откроет сертификат, как только наберёт проходной балл.'
            if course.self_paced else
            '«Поведение сертификата при отображении»: «Сразу после прохождения». '
            'Ученик откроет сертификат, как только наберёт проходной балл.'
        )
    else:
        early_title = (
            'Сертификат доступен только после даты, указанной в расписании'
            if behavior == CertificatesDisplayBehaviors.END_WITH_DATE.value
            else 'Сертификат доступен только после окончания курса'
        )
        early_detail = (
            'Сертификат создаётся, как только ученик наберёт проходной балл, но открыть его ученик сможет позже. '
            'Чтобы он был доступен сразу, в редакторе курса откройте «Расписание и подробности» → '
            '«Поведение сертификата при отображении» и выберите «Сразу после прохождения».'
        )
        if behavior == CertificatesDisplayBehaviors.END.value and not course.end:
            early_detail += ' Дата окончания курса не задана — сейчас ученик не увидит сертификат никогда.'
        if not auto_enabled:
            early_detail += (
                ' Сейчас это поле в редакторе скрыто: оно появляется, только когда включена '
                'автоматическая выдача сертификатов.' if is_superuser else
                ' Сейчас это поле в редакторе скрыто — обратитесь к администратору платформы.'
            )
    checks.append(_check(
        'early', OK if early else WARN, early_title, early_detail,
        None if early else schedule_url, None if early else 'Открыть расписание курса',
    ))

    # Self-generated certificates: «Запросить сертификат» on the progress page. Needs the platform switch
    # (CertificateGenerationConfiguration) and the course setting. With auto generation off it is the only way
    # learners get a certificate, so it is required then; otherwise it is optional (info).
    platform_enabled = CertificateGenerationConfiguration.current().enabled
    course_allowed = CertificateGenerationCourseSetting.is_self_generation_enabled_for_course(course_key)
    self_generation = platform_enabled and course_allowed
    self_action = None
    if self_generation:
        self_detail = 'На странице «Прогресс» ученик, набравший проходной балл, нажимает «Запросить сертификат».'
    elif not platform_enabled:
        self_detail = (
            'Сначала нужно включить управление сертификатами на платформе (см. условия вкладки выше), '
            'затем разрешить выпуск для курса.' if is_superuser else
            'Для этого администратор платформы должен включить управление сертификатами, '
            'после этого выпуск разрешается для курса на этой вкладке.'
        )
    elif auto_enabled:
        # Auto generation already issues the certificate: no button here, see the «auto» note
        self_detail = (
            'Это не нужно: сертификат выдаётся автоматически при сдаче курса, нажимать «Разрешить обучающимся '
            'выпускать себе сертификаты» не требуется.'
        )
    else:
        self_detail = (
            'Разрешите ученикам курса запрашивать сертификат на странице «Прогресс».' if can_fix else
            'Разрешается кнопкой «Разрешить обучающимся выпускать себе сертификаты» ниже на этой вкладке.'
        )
        if can_fix:
            self_action = {
                'url': reverse('robbo_certificates:enable_self_generation', kwargs={'course_id': str(course_key)}),
                'label': 'Разрешить ученикам выпускать сертификаты',
                'confirm': 'Разрешить ученикам этого курса самим запрашивать сертификат на странице «Прогресс»?',
            }
    checks.append(_check(
        'self_generation',
        OK if self_generation else (INFO if auto_enabled else FAIL),
        'Ученики могут сами выпустить сертификат' if self_generation
        else 'Ученики не могут сами выпустить сертификат',
        self_detail, action=self_action,
    ))

    # Stable sort: keep the order of the checks, the special note first, informational ones at the end of the grid
    checks.sort(key=lambda check: {NOTE: 0, INFO: 2}.get(check['status'], 1))
    return checks


def summary(checks):
    """'ready' when nothing fails, else 'not_ready'."""
    return 'not_ready' if any(check['status'] == FAIL for check in checks) else 'ready'
