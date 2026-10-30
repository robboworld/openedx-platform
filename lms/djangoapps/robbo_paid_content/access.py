# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (paid content). See NOTICE at repository root.
"""
Loading a paid block on the free path (lms/djangoapps/courseware/access.py, «load»): denied.

With the «locked» display the error carries a message and the paywall fragment, so the unit shows
«available with full access» and a button to buy it (courseware block_render keeps such blocks and
shows one paywall for a run of denied siblings). With «hidden» it carries none, and the block is
left out. Submitting an answer to a paid problem goes through the same check.
"""

from django.conf import settings
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.http import urlencode
from web_fragments.fragment import Fragment

from opaque_keys.edx.locator import CourseLocator

from common.djangoapps.course_modes.models import CourseMode
from lms.djangoapps.courseware.access_response import AccessError
from lms.djangoapps.robbo_changelog.labels import pick

from . import policy
from .models import PaidContentPolicy

TEXTS = {
    'message': {
        'ru': 'Доступно с полным доступом к курсу',
        'en': 'Available with full access to the course',
    },
    'body': {
        'ru': 'Этот материал входит в полный доступ к курсу.',
        'en': 'This material is part of full access to the course.',
    },
    'button': {'ru': 'Оформить полный доступ за {price}', 'en': 'Get full access for {price}'},
    'not_sold': {
        'ru': 'Сейчас полный доступ к курсу не продаётся. Если он вам нужен, напишите в поддержку.',
        'en': 'Full access to the course is not on sale now. Contact support if you need it.',
    },
}


class PaidContentAccessError(AccessError):
    """The block is paid and the learner is on the free path."""

    def __init__(self, user_message=None, user_fragment=None):
        super().__init__(
            error_code='robbo_paid_content',
            developer_message='Paid content: the learner has no full access to the course',
            user_message=user_message,
            user_fragment=user_fragment,
        )


def checkout(course_key):
    """(absolute link to buy full access, price text), or (None, None) when it is not sold."""
    if not getattr(settings, 'ROBBO_PAYMENTS_ENABLED', False):
        return None, None
    mode = CourseMode.verified_mode_for_course(course_key)
    if mode is None or mode.slug != CourseMode.VERIFIED or not mode.sku or mode.min_price <= 0:
        return None, None
    from lms.djangoapps.robbo_payments.utils import format_checkout_price_display
    query = urlencode({'sku': mode.sku, 'course_run_key': str(course_key)})
    url = f'{settings.LMS_ROOT_URL}{reverse("robbo_payments:basket_add")}?{query}'
    return url, format_checkout_price_display(mode.min_price, (mode.currency or 'rub').upper())


def paywall_fragment(course_key):
    url, price = checkout(course_key)
    return Fragment(render_to_string('robbo_paid_content/paywall.html', {
        'title': pick(TEXTS['message']),
        'body': pick(TEXTS['body']) if url else pick(TEXTS['not_sold']),
        'checkout_url': url,
        'button': pick(TEXTS['button']).format(price=price) if url else '',
    }))


def check_load(block, user, course_key):
    """A PaidContentAccessError for a paid block on the free path, or None. Course staff are checked before."""
    course_key = course_key or getattr(block.scope_ids.usage_id, 'course_key', None)
    if not isinstance(course_key, CourseLocator):  # content libraries and the like: no courses, no policy
        return None
    course_policy = policy.get_policy(course_key)
    if course_policy is None or not policy.is_paid_block(block, course_policy):
        return None
    if policy.has_full_access(user, course_key):
        return None
    if course_policy.display == PaidContentPolicy.DISPLAY_HIDDEN:
        return PaidContentAccessError()
    return PaidContentAccessError(user_message=pick(TEXTS['message']), user_fragment=paywall_fragment(course_key))
