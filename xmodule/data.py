"""
Public data structures for this app.

See OEP-49 for details

Modifications Copyright (C) 2026 Robbo. See NOTICE at repository root.
"""
from enum import Enum


class CertificatesDisplayBehaviors(str, Enum):
    """
    Options for the certificates_display_behavior field of a course

    end: Certificates are available at the end of the course
    end_with_date: Certificates are available after the certificate_available_date (post course end)
    early_no_info: Certificates are available immediately after earning them.

    Only in affect for instructor based courses.
    """
    END = "end"
    END_WITH_DATE = "end_with_date"
    EARLY_NO_INFO = "early_no_info"

    @classmethod
    def includes_value(cls, value):
        return value in set(item.value for item in cls)

    @classmethod
    def normalize(cls, value):
        """
        Robbo: the plain string stored in the course field.

        On Python 3.11 ``str()`` of a member is ``'CertificatesDisplayBehaviors.EARLY_NO_INFO'``, and such strings
        got saved to courses (Studio stored a member instead of its value). They are not valid display behaviors,
        so certificates silently became «available after the course end». Members and those strings map back to
        the value; anything else is returned unchanged.
        """
        if isinstance(value, cls):
            return value.value
        prefix = f'{cls.__name__}.'
        if isinstance(value, str) and value.startswith(prefix) and value[len(prefix):] in cls.__members__:
            return cls[value[len(prefix):]].value
        return value
