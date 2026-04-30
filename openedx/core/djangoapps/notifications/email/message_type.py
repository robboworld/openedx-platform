"""
Email notifications MessageType
"""
from django.conf import settings

from openedx.core.djangoapps.ace_common.message import BaseMessageType


class EmailNotificationMessageType(BaseMessageType):
    """
    Edx-ace MessageType for Email Notifications
    """

    NAME = "notifications"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.options['transactional'] = True
        self.options['from_address'] = settings.NOTIFICATIONS_DEFAULT_FROM_EMAIL
