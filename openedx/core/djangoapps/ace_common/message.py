"""
Base Message types to be used to construct ace messages.
"""


from django.conf import settings

from edx_ace.message import MessageType


class BaseMessageType(MessageType):  # lint-amnesty, pylint: disable=missing-class-docstring
    """
    Subclasses are used for edx-ace transactional email.

    edx-ace passes ``language`` through to ``Message`` unchanged; ``None`` is
    rendered as English. ``personalize`` fills ``None`` with
    ``ACE_EMAIL_DEFAULT_LANGUAGE`` (default ``ru``). Non-empty caller
    ``language`` is preserved (e.g. activation email uses ``ACTIVATION_EMAIL_LANGUAGE``).
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers

        from_address = configuration_helpers.get_value('email_from_address')
        if from_address:
            self.options.update({'from_address': from_address})  # pylint: disable=no-member

    def personalize(self, recipient, language, user_context):
        """
        edx-ace renders with ``Message.language``; ``None`` becomes English.
        Use caller ``language`` when set; otherwise ``ACE_EMAIL_DEFAULT_LANGUAGE``
        from Django settings (default ``ru``).
        """
        # Default ACE locale from Django settings only (stack policy), not SiteConfiguration.
        forced_lang = getattr(settings, 'ACE_EMAIL_DEFAULT_LANGUAGE', 'ru')
        effective_lang = language or forced_lang
        return super().personalize(recipient, effective_lang, user_context)
