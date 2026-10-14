# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (course deletion in Studio). See NOTICE at repository root.
"""
Studio API for deleting a course from the Studio home page (platform staff only).

Does what ``./manage.py cms delete_course <course_id>`` does without ``--remove-assets``:
the course leaves the modulestore and the course team loses its roles. Enrollments, grades,
certificates and payments stay in the database; uploaded files stay in the contentstore.
"""

import logging

from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from cms.djangoapps.contentstore.utils import delete_course
from common.djangoapps.student.models import CourseEnrollment
from common.djangoapps.student.roles import GlobalStaff
from openedx.core.lib.api.view_utils import DeveloperErrorViewMixin, view_auth_classes
from xmodule.modulestore.django import modulestore

log = logging.getLogger(__name__)


@view_auth_classes(is_authenticated=True)
class CourseDeleteView(DeveloperErrorViewMixin, APIView):
    """
    Platform staff only.

    GET    /api/contentstore/v1/robbo/courses/{course_id}
        {"course_id", "display_name", "enrollment_count"} — what the confirmation dialog shows.
    DELETE same URL — deletes the course, 204.
    """

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not GlobalStaff().has_user(request.user):
            self.permission_denied(request)

    def _get_course(self, course_id):
        """(course key, course) or raise 404."""
        try:
            course_key = CourseKey.from_string(course_id)
        except InvalidKeyError as error:
            raise self.api_error(status.HTTP_404_NOT_FOUND, 'Invalid course key.', 'invalid_course_key') from error
        course = modulestore().get_course(course_key, depth=0)
        if course is None:
            raise self.api_error(status.HTTP_404_NOT_FOUND, 'Course not found.', 'course_does_not_exist')
        return course_key, course

    def get(self, request: Request, course_id: str):
        course_key, course = self._get_course(course_id)
        return Response({
            'course_id': str(course_key),
            'display_name': course.display_name_with_default,
            'enrollment_count': CourseEnrollment.objects.filter(course_id=course_key, is_active=True).count(),
        })

    def delete(self, request: Request, course_id: str):
        course_key, _ = self._get_course(course_id)
        log.info('Robbo: %s deletes course %s from Studio home', request.user.username, course_key)
        delete_course(course_key, request.user.id)
        return Response(status=status.HTTP_204_NO_CONTENT)
