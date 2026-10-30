# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (course type: paid access and paid certificate). See NOTICE at repository root.
"""
Studio API for the «Тип курса» settings page: what is paid in a course.

* Full access — the «verified» course mode (robbo_payments sells the upgrade at /basket/add/).
* Certificate — robbo_certificates.CertificateOffer (docs/paid-certificates.md in the meta repo).
* Paid content — robbo_paid_content.PaidContentPolicy: what of the course needs full access, what the
  free path sees instead and how its grade counts (docs/paid-content.md). The «Только полный доступ»
  lock itself is set on sections/subsections in the course outline.

The course team reads the page; only platform staff and superusers change it.
"""

import uuid
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone
from opaque_keys.edx.keys import CourseKey
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from common.djangoapps.course_modes.models import CourseMode
from common.djangoapps.student.auth import has_studio_read_access
from common.djangoapps.student.models import CourseEnrollment
from common.djangoapps.student.roles import GlobalStaff
from lms.djangoapps.robbo_certificates import offers
from lms.djangoapps.robbo_certificates.models import CertificateOffer
from lms.djangoapps.robbo_paid_content import policy as paid_content_policy
from lms.djangoapps.robbo_paid_content.models import PaidContentPolicy
from xmodule.modulestore.django import modulestore
from openedx.core.djangoapps.course_groups.models import CourseUserGroup
from openedx.core.lib.api.view_utils import DeveloperErrorViewMixin, verify_course_exists, view_auth_classes

MAX_PRICE = 1_000_000


class CourseTypeError(Exception):
    """A value of the PUT body is not acceptable; the message is shown to the user."""


def can_edit_course_type(user):
    return bool(user.is_superuser or GlobalStaff().has_user(user))


def _verified_mode(course_key):
    return CourseMode.objects.filter(course_id=course_key, mode_slug=CourseMode.VERIFIED).first()


def _is_selling(mode):
    return mode is not None and (mode.expiration_datetime is None or mode.expiration_datetime > timezone.now())


def _price(value):
    """Whole rubles from 1 to MAX_PRICE (CourseMode.min_price is an integer)."""
    try:
        price = Decimal(str(value).replace(',', '.').strip())
    except (InvalidOperation, ValueError) as exc:
        raise CourseTypeError('Цена — целое число рублей.') from exc
    if price != price.to_integral_value() or not 1 <= price <= MAX_PRICE:
        raise CourseTypeError(f'Цена — целое число рублей от 1 до {MAX_PRICE:,}.'.replace(',', ' '))
    return int(price)


def _cohorts(course_key):
    return CourseUserGroup.objects.filter(course_id=course_key, group_type=CourseUserGroup.COHORT).order_by('name')


def course_type_payload(user, course_key):
    """GET body (snake_case; the MFE camelCases it)."""
    offer = CertificateOffer.objects.filter(course_key=course_key).first()
    mode = _verified_mode(course_key)
    certificate_paid = bool(offer and offer.is_enabled)
    return {
        'can_edit': can_edit_course_type(user),
        'paid_certificates_switch': offers.PAID_CERTIFICATES.is_enabled(),
        'passing_percent': offers.course_min_percent(course_key),
        'certificate': {
            'paid': certificate_paid,
            'price': int(offer.price) if offer else None,
            'min_percent': offer.min_percent if offer else None,
            'free_for_verified': CourseMode.VERIFIED in (offer.free_for_modes or []) if offer else True,
            'free_for_cohorts': sorted(offer.free_for_cohorts.values_list('id', flat=True)) if offer else [],
        },
        'full_access': {
            'paid': _is_selling(mode),
            'price': mode.min_price if mode else None,
            'learners': CourseEnrollment.objects.filter(
                course_id=course_key, mode=CourseMode.VERIFIED, is_active=True,
            ).count(),
        },
        'cohorts': [{'id': cohort.id, 'name': cohort.name} for cohort in _cohorts(course_key)],
        'paid_content': _paid_content_payload(course_key),
    }


def _paid_content_payload(course_key):
    content_policy = PaidContentPolicy.objects.filter(course_key=course_key).first()
    course = modulestore().get_course(course_key, depth=1)
    sections = course.get_children() if course else []
    locked = 0
    for section in sections:
        locked += int(bool(section.robbo_paid_only))
        locked += sum(int(bool(sequence.robbo_paid_only)) for sequence in section.get_children())
    return {
        'enabled': bool(content_policy and content_policy.is_enabled),
        'free_sections': content_policy.free_sections if content_policy else None,
        'graded_paid': bool(content_policy and content_policy.graded_paid),
        'display': content_policy.display if content_policy else PaidContentPolicy.DISPLAY_LOCKED,
        'grading': content_policy.grading if content_policy else PaidContentPolicy.GRADING_ZERO,
        'sections': len(sections),
        'locked': locked,
    }


def _ensure_free_mode(course_key):
    """Paid parts sit on top of a free enrollment: without «honor» or «audit» nobody could enroll for free."""
    if not CourseMode.objects.filter(course_id=course_key, mode_slug__in=(CourseMode.HONOR, CourseMode.AUDIT)).exists():
        CourseMode.objects.create(course_id=course_key, mode_slug=CourseMode.HONOR, mode_display_name='Honor', min_price=0)


def _save_full_access(course_key, data):
    mode = _verified_mode(course_key)
    if data.get('paid'):
        price = _price(data.get('price'))
        if mode is None:
            mode = CourseMode(
                course_id=course_key, mode_slug=CourseMode.VERIFIED, mode_display_name='Полный доступ',
                sku=f'ROBBO-VERIFIED-{uuid.uuid4().hex[:8].upper()}',
            )
        mode.min_price = price
        mode.currency = 'rub'
        # Explicit: sold until staff turn it off here; otherwise publishing the course would set
        # the upgrade deadline from the course end date (course_modes signals)
        mode.expiration_datetime = None
        mode.expiration_datetime_is_explicit = True
        mode.save()
        _ensure_free_mode(course_key)
    elif mode is not None:
        if CourseEnrollment.objects.filter(course_id=course_key, mode=CourseMode.VERIFIED).exists():
            # Learners who paid keep the «Полный доступ» tab; an expired mode is just not sold any more
            if _is_selling(mode):
                mode.expiration_datetime = timezone.now()
                mode.expiration_datetime_is_explicit = True
                mode.save()
        else:
            mode.delete()


def _save_certificate(user, course_key, data):
    offer = CertificateOffer.objects.filter(course_key=course_key).first()
    if not data.get('paid'):
        if offer is not None and offer.is_enabled:
            offer.is_enabled = False
            offer.updated_by = user
            offer.save()
        return

    price = _price(data.get('price'))
    min_percent = data.get('min_percent')
    if min_percent in ('', None):
        min_percent = None
    else:
        try:
            min_percent = int(min_percent)
        except (TypeError, ValueError) as exc:
            raise CourseTypeError('Порог — целое число процентов.') from exc
    message = offers.min_percent_error(course_key, min_percent)
    if message:
        raise CourseTypeError(message)

    cohort_ids = data.get('free_for_cohorts') or []
    if not isinstance(cohort_ids, list):
        raise CourseTypeError('Группы — список.')
    cohorts = list(_cohorts(course_key).filter(id__in=cohort_ids))
    if len(cohorts) != len(set(cohort_ids)):
        raise CourseTypeError('Можно выбрать только группы этого курса.')

    if offer is None:
        offer = CertificateOffer(course_key=course_key)
    offer.is_enabled = True
    offer.price = Decimal(price)
    offer.min_percent = min_percent
    free_modes = [mode for mode in (offer.free_for_modes or []) if mode != CourseMode.VERIFIED]
    if data.get('free_for_verified', True):
        free_modes.append(CourseMode.VERIFIED)
    offer.free_for_modes = free_modes
    offer.updated_by = user
    offer.save()
    offer.free_for_cohorts.set(cohorts)
    _ensure_free_mode(course_key)


def _save_paid_content(user, course_key, data):
    content_policy = PaidContentPolicy.objects.filter(course_key=course_key).first()
    if not data.get('enabled'):
        if content_policy is None or not content_policy.is_enabled:
            return False
        content_policy.is_enabled = False
        content_policy.updated_by = user
        content_policy.save()
        return True

    free_sections = data.get('free_sections')
    if free_sections in ('', None):
        free_sections = None
    else:
        try:
            free_sections = int(free_sections)
        except (TypeError, ValueError) as exc:
            raise CourseTypeError('Число бесплатных разделов — целое число.') from exc
        if not 0 <= free_sections <= 1000:
            raise CourseTypeError('Число бесплатных разделов — от 0 до 1000.')
    display = data.get('display') or PaidContentPolicy.DISPLAY_LOCKED
    if display not in dict(PaidContentPolicy.DISPLAY_CHOICES):
        raise CourseTypeError('Неизвестный способ показа платного.')
    grading = data.get('grading') or PaidContentPolicy.GRADING_ZERO
    if grading not in dict(PaidContentPolicy.GRADING_CHOICES):
        raise CourseTypeError('Неизвестный способ учёта оценок.')

    if content_policy is None:
        content_policy = PaidContentPolicy(course_key=course_key)
    content_policy.is_enabled = True
    content_policy.free_sections = free_sections
    content_policy.graded_paid = bool(data.get('graded_paid'))
    content_policy.display = display
    content_policy.grading = grading
    content_policy.updated_by = user
    content_policy.save()
    return True


def _refresh_paid_content(course_key):
    """The learning_sequences outline carries which sections/subsections are paid: rebuild it now."""
    from cms.djangoapps.contentstore.outlines import update_outline_from_modulestore
    paid_content_policy.clear_policy_cache()
    transaction.on_commit(lambda: update_outline_from_modulestore(course_key))


@view_auth_classes(is_authenticated=True)
class CourseTypeView(DeveloperErrorViewMixin, APIView):
    """
    GET  /api/contentstore/v1/robbo/course-type/{course_id}
        {"can_edit": bool, "paid_certificates_switch": bool, "passing_percent": 50,
         "certificate": {"paid", "price", "min_percent", "free_for_verified", "free_for_cohorts": [id]},
         "full_access": {"paid", "price", "learners"},
         "cohorts": [{"id", "name"}],
         "paid_content": {"enabled", "free_sections", "graded_paid", "display": "locked" | "hidden",
                          "grading": "zero" | "excluded", "sections", "locked"}}
        Course team (Studio read access).
    PUT  same URL, body {"certificate": {...}, "full_access": {...}} (each optional) — platform staff
        and superusers only; returns the GET body or {"error": "<Russian message>"} with 400.
    """

    @verify_course_exists()
    def get(self, request: Request, course_id: str):
        course_key = CourseKey.from_string(course_id)
        if not has_studio_read_access(request.user, course_key):
            self.permission_denied(request)
        return Response(course_type_payload(request.user, course_key))

    @verify_course_exists()
    def put(self, request: Request, course_id: str):
        course_key = CourseKey.from_string(course_id)
        if not can_edit_course_type(request.user):
            self.permission_denied(request)
        try:
            with transaction.atomic():
                if isinstance(request.data.get('full_access'), dict):
                    _save_full_access(course_key, request.data['full_access'])
                if isinstance(request.data.get('certificate'), dict):
                    _save_certificate(request.user, course_key, request.data['certificate'])
                if isinstance(request.data.get('paid_content'), dict):
                    if _save_paid_content(request.user, course_key, request.data['paid_content']):
                        _refresh_paid_content(course_key)
        except CourseTypeError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(course_type_payload(request.user, course_key))
