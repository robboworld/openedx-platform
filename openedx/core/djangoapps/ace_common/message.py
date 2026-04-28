"""
Base Message types to be used to construct ace messages.
"""


from django.conf import settings

from edx_ace.message import MessageType

from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers


class BaseMessageType(MessageType):  # lint-amnesty, pylint: disable=missing-class-docstring
    """
    Subclasses are used for edx-ace transactional email.

    edx-ace passes ``language`` through to ``Message`` unchanged; ``None`` is
    rendered as English. ``personalize`` fills ``None`` with
    ``ACE_EMAIL_DEFAULT_LANGUAGE`` (default ``ru``). Non-empty caller
    ``language`` is preserved (e.g. ``pref-lang`` or site fallback from
    ``compose_activation_email``).
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from_address = configuration_helpers.get_value('email_from_address')
        if from_address:
            self.options.update({'from_address': from_address})  # pylint: disable=no-member

    def personalize(self, recipient, language, user_context):
        """
        edx-ace renders with ``Message.language``; ``None`` becomes English.
        Use caller ``language`` when set; otherwise Robbo fallback (site config or
        ``ACE_EMAIL_DEFAULT_LANGUAGE``, default ``ru``).
        """
        forced_lang = configuration_helpers.get_value(
            'ACE_EMAIL_DEFAULT_LANGUAGE',
            getattr(settings, 'ACE_EMAIL_DEFAULT_LANGUAGE', 'ru'),
        )
        effective_lang = language or forced_lang
        return super().personalize(recipient, effective_lang, user_context)
