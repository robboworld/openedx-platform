# Copyright (C) 2024-2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of the Robbo Open edX distribution. See NOTICE at repository root.

"""
Access rules for the Robbo global analytics page.
"""
from __future__ import annotations

from common.djangoapps.student.roles import (
    CourseInstructorRole,
    GlobalStaff,
    UserBasedRole,
)


def can_access_robbo_global_analytics(user) -> bool:
    """
    Return True for platform administrators and course instructors.

    Course staff without the instructor role does not get access.
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    if not user.is_active:
        return False
    if GlobalStaff().has_user(user) or user.is_superuser:
        return True
    return UserBasedRole(user, CourseInstructorRole.ROLE).courses_with_role().exists()
