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
from openedx.core.djangoapps.user_api.models import UserPreference

# Course-level and organization-level roles of the course team (org roles reuse the names,
# with an empty course), plus the right to create courses in Studio.
COURSE_TEAM_ROLES = ('instructor', 'staff', 'limited_staff', 'course_creator_group', 'org_course_creator_group')

# Where «Что нового» sits in the header for the course team and staff (account settings, «Оформление»):
# a separate button next to the notifications (default) or an item of the profile menu with a dot.
PLACEMENT_PREFERENCE = 'robbo-whats-new-placement'
PLACEMENT_BUTTON = 'button'
PLACEMENT_MENU = 'menu'
PLACEMENTS = (PLACEMENT_BUTTON, PLACEMENT_MENU)


def can_view(user):
    """«Что нового» is for signed-in users with an activated account; the rest see no button or page."""
    return bool(user is not None and user.is_authenticated and user.is_active)


def viewer_audiences(user):
    """Audience codes ``user`` may see; empty for guests and accounts not activated yet."""
    if not can_view(user):
        return frozenset()
    audiences = {'all'}
    if user.is_superuser:
        return frozenset(audiences | {'authors', 'teachers', 'platform_staff', 'platform_admins'})
    if user.is_staff:
        return frozenset(audiences | {'authors', 'teachers', 'platform_staff'})
    if CourseAccessRole.objects.filter(user=user, role__in=COURSE_TEAM_ROLES).exists():
        audiences |= {'authors', 'teachers'}
    return frozenset(audiences)


def is_learner(user):
    """Sees only entries for everyone: no course team role, not platform staff."""
    return viewer_audiences(user) == {'all'}


def can_choose_placement(user):
    """The course team and staff choose where «Что нового» sits; learners always have it in the profile menu."""
    return can_view(user) and not is_learner(user)


def placement(user):
    """``menu`` or ``button`` for ``user``; learners always ``menu``."""
    if is_learner(user):
        return PLACEMENT_MENU
    value = UserPreference.get_value(user, PLACEMENT_PREFERENCE)
    return value if value in PLACEMENTS else PLACEMENT_BUTTON


def set_placement(user, value):
    UserPreference.objects.update_or_create(user=user, key=PLACEMENT_PREFERENCE, defaults={'value': value})


def in_profile_menu(user):
    """«Что нового» as a profile menu item with a dot on the menu button instead of a header button."""
    return placement(user) == PLACEMENT_MENU


def is_platform_staff(audiences):
    """Platform staff and administrators also see release versions (to talk to support)."""
    return 'platform_staff' in audiences or 'platform_admins' in audiences
