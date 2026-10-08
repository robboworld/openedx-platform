# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (site changelog). See NOTICE at repository root.
"""
Which «Что нового» audiences a user may see.

Levels stack bottom-up: the course team sees entries for authors and teachers, platform staff
also sees its own, a platform administrator sees everything. Learners see only ``all``.
"""

from common.djangoapps.student.models import CourseAccessRole

# Course-level and organization-level roles of the course team (org roles reuse the names,
# with an empty course), plus the right to create courses in Studio.
COURSE_TEAM_ROLES = ('instructor', 'staff', 'limited_staff', 'course_creator_group', 'org_course_creator_group')


def viewer_audiences(user):
    """Audience codes ``user`` may see; empty for anonymous users (the page needs a login)."""
    if user is None or not user.is_authenticated:
        return frozenset()
    audiences = {'all'}
    if user.is_superuser:
        return frozenset(audiences | {'authors', 'teachers', 'platform_staff', 'platform_admins'})
    if user.is_staff:
        return frozenset(audiences | {'authors', 'teachers', 'platform_staff'})
    if CourseAccessRole.objects.filter(user=user, role__in=COURSE_TEAM_ROLES).exists():
        audiences |= {'authors', 'teachers'}
    return frozenset(audiences)


def is_platform_staff(audiences):
    """Platform staff and administrators also see release versions (to talk to support)."""
    return 'platform_staff' in audiences or 'platform_admins' in audiences
