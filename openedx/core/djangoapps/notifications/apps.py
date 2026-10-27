"""
Config for notifications app
"""

from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    """
    Config for notifications app
    """
    name = 'openedx.core.djangoapps.notifications'
    verbose_name = 'Notifications'

    def ready(self):
        """
        Import signals
        """
        # pylint: disable=unused-import
        from . import handlers
        from .email import tasks
        # Robbo: stored settings «Для всех курсов» (new course preferences start with them).
        from . import robbo_account  # noqa: F401
        # Robbo: «Сразу» emails — imported here so Celery workers register the task at start.
        from .email import robbo_immediate  # noqa: F401
        # Robbo: notifications from platform events (certificates, enrollments, Studio, …).
        from .robbo_events import connect as connect_events
        connect_events()
        # Robbo: learner progress notifications for the course team (LMS only: grades signals).
        from django.conf import settings
        if getattr(settings, 'ROOT_URLCONF', '') == 'lms.urls':
            from .robbo_progress import connect
            connect()
