# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution. See NOTICE at repository root.

"""
Robbo stack profile of this branch (online / skill / courses).

Each profile branch keeps its own value here. LMS and Studio headers show its
first letter next to the logo to platform admins, so they can tell the sites apart.
"""

ROBBO_STACK_PROFILE = 'online'


def robbo_stack_letter() -> str:
    """First letter of the profile, upper-cased: O / S / C."""
    return ROBBO_STACK_PROFILE[:1].upper()


def user_can_see_robbo_stack_badge(user) -> bool:
    """Platform superuser or global staff (``is_staff``), as for other admin-only header items."""
    if user is None or not user.is_authenticated:
        return False
    return bool(getattr(user, 'is_superuser', False) or getattr(user, 'is_staff', False))
