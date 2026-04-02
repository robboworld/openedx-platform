"""
This module contains various configuration settings via
waffle switches for the notifications app.
"""

from openedx.core.djangoapps.waffle_utils import CourseWaffleFlag, WaffleFlag

WAFFLE_NAMESPACE = 'notifications'

# .. toggle_name: notifications.disable_notifications
# .. toggle_implementation: WaffleFlag
# .. toggle_default: False
# .. toggle_description: Waffle flag to disable the Notifications feature
# .. toggle_use_cases: open_edx
# .. toggle_creation_date: 2026-02-03
# .. toggle_target_removal_date: None
# .. toggle_warning: When the flag is ON, Notifications feature is disabled.
# .. toggle_tickets: None
DISABLE_NOTIFICATIONS = WaffleFlag(f'{WAFFLE_NAMESPACE}.disable_notifications', __name__)

# .. toggle_name: notifications.disable_email_notifications
# .. toggle_implementation: WaffleFlag
# .. toggle_default: False
# .. toggle_description: Waffle flag to disable the Email Notifications feature
# .. toggle_use_cases: open_edx
# .. toggle_creation_date: 2026-02-03
# .. toggle_target_removal_date: None
# .. toggle_warning: When the flag is ON, Email Notifications feature will be disabled.
# .. toggle_tickets: INF-1259
DISABLE_EMAIL_NOTIFICATIONS = WaffleFlag(f'{WAFFLE_NAMESPACE}.disable_email_notifications', __name__)

# .. toggle_name: notifications.enable_push_notifications
# .. toggle_implementation: CourseWaffleFlag
# .. toggle_default: False
# .. toggle_description: Waffle flag to enable push Notifications feature on mobile devices
# .. toggle_use_cases: temporary
# .. toggle_creation_date: 2025-05-27
# .. toggle_target_removal_date: 2026-05-27
# .. toggle_warning: When the flag is ON, Notifications will go through ace push channels.
ENABLE_PUSH_NOTIFICATIONS = CourseWaffleFlag(f'{WAFFLE_NAMESPACE}.enable_push_notifications', __name__)

# .. toggle_name: notifications.enable_ora_reminders
# .. toggle_implementation: WaffleFlag
# .. toggle_default: False
# .. toggle_description: Waffle flag to enable ORA reminder notifications for learners
#   who have pending self or peer review steps after submitting an ORA response.
# .. toggle_use_cases: open_edx
# .. toggle_creation_date: 2026-03-26
# .. toggle_target_removal_date: None
# .. toggle_warning: When the flag is ON, learners will receive periodic reminders
#   for incomplete peer/self review steps.
# .. toggle_tickets: None
ENABLE_ORA_REMINDERS = WaffleFlag(f'{WAFFLE_NAMESPACE}.enable_ora_reminders', __name__)

