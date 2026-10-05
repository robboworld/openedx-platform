# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (certificate designs). See NOTICE at repository root.
"""
Studio API for certificate designs.

* ``certificates/{course_id}/robbo-design`` — designs a course can use and the selected one
  (course team with write access).
* ``robbo/certificate-designs[/{design_id}]`` — upload, edit and archive designs
  (platform staff only).
"""

import json

from django.core.exceptions import ValidationError
from django.db import transaction
from opaque_keys.edx.keys import CourseKey
from PIL import Image, UnidentifiedImageError
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from common.djangoapps.student.auth import has_studio_write_access
from common.djangoapps.student.roles import GlobalStaff
from lms.djangoapps.robbo_certificates import designs as robbo_designs
from lms.djangoapps.robbo_certificates.fields import (
    COURSE_HOURS_KEY,
    MAX_COURSE_HOURS,
    FieldsValidationError,
    default_fields,
    parse_hours,
    validate_fields,
)
from lms.djangoapps.robbo_certificates.models import CertificateDesign
from openedx.core.lib.api.view_utils import DeveloperErrorViewMixin, verify_course_exists, view_auth_classes
from xmodule.modulestore.django import modulestore

BACKGROUND_FORMATS = {'PNG': 'png', 'JPEG': 'jpg'}
BACKGROUND_MAX_BYTES = 10 * 1024 * 1024
BACKGROUND_MIN_WIDTH = 1000
PICKER_DESIGN_KEYS = ('id', 'kind', 'origin', 'uses_hours', 'title', 'description', 'preview_image_url')


def _error(message, code=status.HTTP_400_BAD_REQUEST):
    return Response({'error': message}, status=code)


@view_auth_classes(is_authenticated=True)
class CourseCertificateDesignView(DeveloperErrorViewMixin, APIView):
    """
    GET  /api/contentstore/v1/certificates/{course_id}/robbo-design
        {"designs": [{"id", "kind", "origin": "custom" | "builder", "uses_hours", "title", "description",
                      "preview_image_url"}],
         "selected": "olympiad",
         "default": "olympiad", "preview_query_param": "robbo_design", "can_manage_designs": false,
         "course_hours": 72}
    PUT  same URL, body {"design": "<id>"} and/or {"course_hours": 72 | null} — stores them in the
        course's Advanced Settings → "Certificate Web/HTML View Overrides" and returns the GET payload.
    """

    def _check_access(self, request, course_key):
        if not has_studio_write_access(request.user, course_key):
            self.permission_denied(request)

    def _payload(self, request, course):
        stored = (course.cert_html_view_overrides or {}).get(robbo_designs.DESIGN_OVERRIDE_KEY)
        designs = robbo_designs.list_designs()
        return {
            'designs': [
                {key: design[key] for key in PICKER_DESIGN_KEYS}
                for design in designs
            ],
            'selected': robbo_designs.resolve_design(stored),
            'default': robbo_designs.DEFAULT_DESIGN,
            'preview_query_param': robbo_designs.PREVIEW_QUERY_PARAM,
            'can_manage_designs': GlobalStaff().has_user(request.user),
            'course_hours': parse_hours((course.cert_html_view_overrides or {}).get(COURSE_HOURS_KEY)),
        }

    @verify_course_exists()
    def get(self, request: Request, course_id: str):
        course_key = CourseKey.from_string(course_id)
        self._check_access(request, course_key)
        return Response(self._payload(request, modulestore().get_course(course_key)))

    @verify_course_exists()
    def put(self, request: Request, course_id: str):
        course_key = CourseKey.from_string(course_id)
        self._check_access(request, course_key)

        changes = {}
        if 'design' in request.data:
            design_id = str(request.data.get('design') or '')
            if design_id not in robbo_designs.design_ids():
                return _error('Такого оформления нет.')
            changes[robbo_designs.DESIGN_OVERRIDE_KEY] = design_id
        if 'course_hours' in request.data:
            raw_hours = request.data.get('course_hours')
            if raw_hours in (None, ''):
                changes[COURSE_HOURS_KEY] = None
            else:
                hours = parse_hours(raw_hours)
                if hours is None:
                    return _error(f'Объём курса — целое число часов от 1 до {MAX_COURSE_HOURS}.')
                # String, as the "green" sheet on robbo/courses reads it
                changes[COURSE_HOURS_KEY] = str(hours)
        if not changes:
            return _error('Нечего сохранять.')

        store = modulestore()
        with store.bulk_operations(course_key):
            course = store.get_course(course_key)
            overrides = dict(course.cert_html_view_overrides or {})
            for key, value in changes.items():
                if value is None:
                    overrides.pop(key, None)
                else:
                    overrides[key] = value
            if overrides != (course.cert_html_view_overrides or {}):
                course.cert_html_view_overrides = overrides
                course = store.update_item(course, request.user.id)
        return Response(self._payload(request, course))


def _check_background(upload):
    """Return an error message for a bad background upload, or None."""
    if upload.size > BACKGROUND_MAX_BYTES:
        return 'Фон должен быть не больше 10 МБ.'
    try:
        with Image.open(upload) as image:
            image_format, width, height = image.format, image.width, image.height
            image.verify()
    except (UnidentifiedImageError, OSError, ValidationError):
        return 'Фон должен быть изображением PNG или JPEG.'
    finally:
        upload.seek(0)
    if image_format not in BACKGROUND_FORMATS:
        return 'Фон должен быть изображением PNG или JPEG.'
    if width < BACKGROUND_MIN_WIDTH or width <= height:
        return (
            f'Нужен горизонтальный фон шириной от {BACKGROUND_MIN_WIDTH} px '
            '(лучше A4: 3508 × 2480; другие пропорции растягиваются до A4).'
        )
    upload.name = f'background.{BACKGROUND_FORMATS[image_format]}'
    return None


@view_auth_classes(is_authenticated=True)
class CertificateDesignListView(DeveloperErrorViewMixin, APIView):
    """
    Platform staff only.

    GET  /api/contentstore/v1/robbo/certificate-designs
        {"designs": [{"id", "kind": "uploaded", "title", "description", "background_url", "fields",
                      "is_active"}], "default_fields": [...]}
    POST multipart: title, description, fields (JSON string), background (PNG/JPEG file)
    """

    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not GlobalStaff().has_user(request.user):
            self.permission_denied(request)

    def get(self, request: Request):
        return Response({
            'designs': [
                robbo_designs.uploaded_design_payload(design)
                for design in CertificateDesign.objects.filter(is_active=True)
            ],
            'default_fields': default_fields(),
        })

    def post(self, request: Request):
        design = CertificateDesign(created_by=request.user)
        return _save_design(request, design, created=True)


@view_auth_classes(is_authenticated=True)
class CertificateDesignDetailView(DeveloperErrorViewMixin, APIView):
    """
    Platform staff only.

    PUT    /api/contentstore/v1/robbo/certificate-designs/{design_id} — same fields as POST,
           background optional (keeps the current one). Custom designs (is_custom) answer 403.
    DELETE same URL — archives the design; courses that used it fall back to the default design.
    """

    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not GlobalStaff().has_user(request.user):
            self.permission_denied(request)

    def _get(self, design_id):
        """(design, error response). Custom designs (dev team) are managed in Django admin only."""
        design = CertificateDesign.objects.filter(slug=design_id, is_active=True).first()
        if not design:
            return None, _error('Оформление не найдено.', status.HTTP_404_NOT_FOUND)
        if design.is_custom:
            return None, _error('Кастомное оформление меняет команда разработки.', status.HTTP_403_FORBIDDEN)
        return design, None

    def put(self, request: Request, design_id: str):
        design, error = self._get(design_id)
        if error:
            return error
        return _save_design(request, design, created=False)

    def delete(self, request: Request, design_id: str):
        design, error = self._get(design_id)
        if error:
            return error
        design.is_active = False
        design.save(update_fields=['is_active', 'modified'])
        return Response(status=status.HTTP_204_NO_CONTENT)


def _save_design(request, design, created):
    title = str(request.data.get('title') or '').strip()
    if not title:
        return _error('Введите название оформления.')
    if len(title) > 255:
        return _error('Название длиннее 255 символов.')

    raw_fields = request.data.get('fields', '[]')
    try:
        fields = validate_fields(json.loads(raw_fields) if isinstance(raw_fields, str) else raw_fields)
    except (ValueError, TypeError) as exc:
        message = str(exc) if isinstance(exc, FieldsValidationError) else 'Список полей имеет неверный формат.'
        return _error(message)

    background = request.FILES.get('background')
    if background:
        problem = _check_background(background)
        if problem:
            return _error(problem)
    elif created:
        return _error('Загрузите фон сертификата.')

    with transaction.atomic():
        design.title = title
        design.description = str(request.data.get('description') or '').strip()[:2000]
        design.fields = fields
        old_background = design.background.name if design.background and background else None
        if background:
            design.background = background
        design.save()
    if old_background:
        design.background.storage.delete(old_background)

    return Response(
        robbo_designs.uploaded_design_payload(design),
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )
