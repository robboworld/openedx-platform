"""
Contentstore Application Configuration

Above-modulestore level signal handlers are connected here.
"""


from django.apps import AppConfig


class ContentstoreConfig(AppConfig):
    """
    Application Configuration for Contentstore.
    """
    name = 'cms.djangoapps.contentstore'

    def ready(self):
        """
        Connect handlers to signals.
        """
        # Can't import models at module level in AppConfigs, and models get
        # included from the signal handlers
        from .signals import handlers  # pylint: disable=unused-import
        from .robbo_ora_i18n import patch_ora_xblock_i18n, patch_robbo_ora_django_catalog
        from .robbo_ora_limits import patch_ora_studio_editor, patch_ora_student_view
        from .robbo_ora_templates import patch_ora_creation_templates

        patch_ora_xblock_i18n()
        patch_robbo_ora_django_catalog()
        patch_ora_studio_editor()
        patch_ora_student_view()
        patch_ora_creation_templates()
