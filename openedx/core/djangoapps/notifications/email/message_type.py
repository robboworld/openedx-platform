"""
Email notifications MessageType
"""
from openedx.core.djangoapps.ace_common.message import BaseMessageType
from openedx.core.djangoapps.notifications.robbo_texts import notification_from_email


class EmailNotificationMessageType(BaseMessageType):
    """
    Edx-ace MessageType for Email Notifications
    """

    NAME = "notifications"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.options['transactional'] = True
        # Robbo: the site sender unless NOTIFICATIONS_DEFAULT_FROM_EMAIL is really set (robbo_texts.py).
        self.options['from_address'] = notification_from_email()
