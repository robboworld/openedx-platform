# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (course key case guard). See NOTICE at repository root.
"""
Refuse a new course key that differs from an earlier course only by letter case.

MySQL compares course keys case-insensitively, Python does not. Rows a deleted course leaves behind
(enrollments, modes, progress) under course-v1:Robbo+X attach to a new course-v1:ROBBO+X but keep the
old key: the catalog failed with KeyError, learners of the old course showed up as enrolled and their
course cards led to 404. The modulestore check (DuplicateCourseError) only sees courses that still
exist, so this one looks at the data such a course leaves behind. With the old spelling the new course
picks the rows up consistently, as Open edX does when a course is recreated under the same key.
"""
from django.db import connection

from xmodule.modulestore.exceptions import DuplicateCourseError

# Tables whose course key column outlives the course.
COURSE_KEY_COLUMNS = (
    ('course_overviews_courseoverview', 'id'),
    ('course_modes_coursemode', 'course_id'),
    ('student_courseenrollment', 'course_id'),
    ('student_courseenrollmentallowed', 'course_id'),
    ('student_courseaccessrole', 'course_id'),
    ('courseware_studentmodule', 'course_id'),
    ('grades_persistentcoursegrade', 'course_id'),
    ('certificates_generatedcertificate', 'course_id'),
)


class CourseKeyCaseConflictError(DuplicateCourseError):
    """
    Data of a course whose key differs from the new one only by letter case exists.
    """
    def __init__(self, course_key, stored_key):
        super().__init__(course_key, stored_key)
        self.stored_key = stored_key


def find_course_key_case_variant(course_key):
    """
    Return the stored spelling of course_key if rows exist under the same key in another letter case.
    """
    if connection.vendor != 'mysql':
        return None  # SQLite compares these columns case-sensitively, the clash cannot happen there.
    key = str(course_key)
    tables = set(connection.introspection.table_names())
    with connection.cursor() as cursor:
        for table, column in COURSE_KEY_COLUMNS:
            if table not in tables:
                continue
            cursor.execute(
                f'SELECT {column} FROM {table} '
                f'WHERE {column} = %s AND CAST({column} AS BINARY) <> CAST(%s AS BINARY) LIMIT 1',
                [key, key],
            )
            row = cursor.fetchone()
            if row:
                return row[0]
    return None


def check_course_key_case(course_key):
    """
    Raise CourseKeyCaseConflictError if course_key differs from an earlier course only by letter case.
    """
    stored_key = find_course_key_case_variant(course_key)
    if stored_key:
        raise CourseKeyCaseConflictError(course_key, stored_key)


def course_key_case_error_message(error):
    """
    Message for the course creation form in the course editor, in the interface language.
    """
    from xmodule.course_metadata_utils import is_russian_language  # pylint: disable=import-outside-toplevel
    if is_russian_language():
        return (
            f'Курс {error.stored_key} уже создавали раньше: новый код отличается от него только заглавными '
            f'и строчными буквами. Напишите организацию, номер и запуск курса точно так же, как в '
            f'{error.stored_key}, или выберите другой код курса.'
        )
    return (
        f'Course {error.stored_key} existed before, and the new code differs from it only in upper and '
        f'lower case letters. Spell the organization, course number and run exactly as in '
        f'{error.stored_key}, or choose a different course code.'
    )
