# Copyright (C) 2024-2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (YooKassa checkout). See NOTICE at repository root.

"""Resolve checkout catalog entries from CourseMode."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from common.djangoapps.course_modes.models import CourseMode
from opaque_keys.edx.keys import CourseKey
from xmodule.modulestore.django import modulestore


@dataclass(frozen=True)
class CatalogProduct:
    """Verified product resolved from CourseMode."""

    course_key: CourseKey
    sku: str
    amount: Decimal
    currency: str
    mode_slug: str
    course_name: str


class CatalogError(Exception):
    """Base catalog resolution error."""


class ProductNotFound(CatalogError):
    """SKU or course mode could not be resolved."""


class InvalidUpgradeProduct(CatalogError):
    """Product is not a supported verified upgrade."""


def resolve_verified_product(course_run_key: str, sku: str) -> CatalogProduct:
    """
    Resolve a verified CourseMode product for checkout.

    Raises ProductNotFound or InvalidUpgradeProduct when validation fails.
    """
    try:
        course_key = CourseKey.from_string(course_run_key)
    except Exception as exc:
        raise ProductNotFound(f'Invalid course_run_key: {course_run_key}') from exc

    verified_mode = CourseMode.verified_mode_for_course(course_key)
    if not verified_mode:
        raise ProductNotFound(f'Course {course_run_key} has no verified mode')

    if verified_mode.sku != sku:
        raise ProductNotFound(
            f'SKU mismatch for course {course_run_key}: expected {verified_mode.sku!r}, got {sku!r}'
        )

    if verified_mode.min_price <= 0:
        raise InvalidUpgradeProduct(f'Verified mode for {course_run_key} is not a paid product')

    course = modulestore().get_course(course_key)
    course_name = course.display_name_with_default if course else str(course_key)

    mode_slug = getattr(verified_mode, 'mode_slug', None) or getattr(verified_mode, 'slug', None)

    return CatalogProduct(
        course_key=course_key,
        sku=sku,
        amount=Decimal(verified_mode.min_price).quantize(Decimal('0.01')),
        currency=(verified_mode.currency or 'rub').upper(),
        mode_slug=mode_slug,
        course_name=course_name,
    )


def get_first_sku_from_query(query_sku) -> Optional[str]:
    """Return the first SKU from a query param (supports repeated sku keys)."""
    if not query_sku:
        return None
    if isinstance(query_sku, (list, tuple)):
        return query_sku[0] if query_sku else None
    return str(query_sku)
