# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution. See NOTICE at repository root.
"""
Notifications button for the Robbo headers: a bell with the unseen counter and a panel with the
latest notifications, served by the LMS to its pages and every MFE header (like «Что нового»).

The data comes from the stock notifications API (``openedx.core.djangoapps.notifications``);
this app only serves the widget script.
"""
