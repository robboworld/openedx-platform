# Copyright (C) 2024-2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only

"""Robbo ORA: per-block max file uploads and Studio template overrides."""

from pathlib import Path

from django.conf import settings
from voluptuous import Optional, Schema
from xblock.fields import Integer, Scope

ROBBO_ORA_DEFAULT_MAX_FILES_COUNT = getattr(settings, 'ROBBO_ORA_DEFAULT_MAX_FILES_COUNT', 1)
ROBBO_ORA_MAX_FILES_COUNT_CAP = getattr(settings, 'ROBBO_ORA_MAX_FILES_COUNT_CAP', 20)
ROBBO_ORA_DEFAULT_MAX_FILE_BYTES = 5 * 1000 * 1000  # 5 MB


def _robbo_ora_max_file_upload_bytes():
    return getattr(settings, 'STUDENT_FILEUPLOAD_MAX_SIZE', ROBBO_ORA_DEFAULT_MAX_FILE_BYTES)

_TEMPLATE_DIR = Path(__file__).resolve().parent / 'templates' / 'legacy' / 'edit'
_TEMPLATE_OVERRIDE = _TEMPLATE_DIR / 'oa_edit_basic_settings_list.html'
_CRITERION_TEMPLATE_OVERRIDE = _TEMPLATE_DIR / 'oa_edit_criterion.html'
_LMS_TEMPLATE_DIR = Path(__file__).resolve().parent / 'templates' / 'legacy'
_RESPONSE_TEMPLATE_DIR = _LMS_TEMPLATE_DIR / 'response'
_UPLOADED_FILE_TEMPLATE_OVERRIDE = _LMS_TEMPLATE_DIR / 'oa_uploaded_file.html'
_RESPONSE_TEMPLATE_OVERRIDE = _RESPONSE_TEMPLATE_DIR / 'oa_response.html'

_STUDIO_HINT_CSS = """
<style type="text/css">
#openassessment-editor .setting-help,
#openassessment-editor .openassessment_description,
#openassessment-editor .openassessment_tab_instructions,
#openassessment-editor .tip.setting-help {
    color: #000 !important;
}
</style>
"""


def _effective_max_files_count(block):
    count = getattr(block, 'max_files_count', None)
    if not count or count < 1:
        count = ROBBO_ORA_DEFAULT_MAX_FILES_COUNT
    return min(int(count), ROBBO_ORA_MAX_FILES_COUNT_CAP)


class _RobboOraFilesLimitMixin:
    """Mixin registered at runtime so max_files_count gets a proper field name."""

    max_files_count = Integer(
        display_name='Maximum File Uploads',
        default=ROBBO_ORA_DEFAULT_MAX_FILES_COUNT,
        scope=Scope.settings,
    )


def _register_max_files_count_field(open_assessment_block):
    """
    Register max_files_count via mixin.

    Assigning Integer() into fields{} at runtime leaves field.name='unknown' and
    breaks LMS staff preview (KeyError in add_staff_markup).
    """
    existing = open_assessment_block.fields.get('max_files_count')
    if existing is not None and getattr(existing, 'name', None) == 'unknown':
        del open_assessment_block.fields['max_files_count']

    if _RobboOraFilesLimitMixin not in open_assessment_block.__bases__:
        open_assessment_block.__bases__ = (
            _RobboOraFilesLimitMixin,
        ) + open_assessment_block.__bases__


def patch_ora_runtime_limits():
    """Runtime file-upload cap (CMS + LMS)."""
    from openassessment.xblock.openassessmentblock import OpenAssessmentBlock

    _register_max_files_count_field(OpenAssessmentBlock)

    if getattr(OpenAssessmentBlock, '_robbo_runtime_limits_patched', False):
        return

    OpenAssessmentBlock.MAX_FILES_COUNT = property(
        lambda self: _effective_max_files_count(self),
    )
    OpenAssessmentBlock._robbo_runtime_limits_patched = True


def patch_ora_studio_editor():
    """Studio editor schema, template override, and save handler (CMS only)."""
    from openassessment.xblock import studio_mixin as studio_mixin_module
    from openassessment.xblock.openassessmentblock import OpenAssessmentBlock
    from openassessment.xblock.utils import schema as schema_module
    from django.contrib.staticfiles.storage import staticfiles_storage
    from django.template import engines
    from django.template.loader import get_template as django_get_template

    if getattr(OpenAssessmentBlock, '_robbo_studio_editor_patched', False):
        return

    patch_ora_runtime_limits()

    schema_dict = dict(schema_module.EDITOR_UPDATE_SCHEMA.schema)
    schema_dict[Optional('max_files_count')] = int
    updated_schema = Schema(schema_dict)
    # studio_mixin imports EDITOR_UPDATE_SCHEMA at load time; patch both bindings.
    schema_module.EDITOR_UPDATE_SCHEMA = updated_schema
    studio_mixin_module.EDITOR_UPDATE_SCHEMA = updated_schema

    original_editor_context = OpenAssessmentBlock.editor_context

    def editor_context(self):
        from .robbo_ora_defaults import localized_necessity_options
        from .robbo_ora_i18n import get_robbo_ora_runtime_catalog

        context = original_editor_context(self)
        context['max_files_count'] = _effective_max_files_count(self)
        max_upload_mb = _robbo_ora_max_file_upload_bytes() // (1000 * 1000)
        context['max_upload_mb'] = max_upload_mb
        context['necessity_options'] = localized_necessity_options()
        catalog = get_robbo_ora_runtime_catalog()
        context['file_upload_max_size_help'] = catalog[
            'Maximum size per file: %(max_mb)s MB.'
        ] % {'max_mb': max_upload_mb}
        context['file_upload_description_help'] = catalog[
            'Learners must enter a short description for each file before uploading. '
            'This requirement is built into Open Response Assessment and cannot be turned off in these settings.'
        ]
        return context

    OpenAssessmentBlock.editor_context = editor_context

    from xblock.core import XBlock

    original_update = OpenAssessmentBlock.update_editor_context
    # StudioMixin.update_editor_context is wrapped by @XBlock.json_handler; call the
    # inner implementation and re-register the handler on our wrapper (replacing the
    # method without @json_handler breaks ORA save with NoSuchHandlerError / HTTP 404).
    if getattr(original_update, '_is_xblock_handler', False):
        original_update = original_update.__wrapped__

    def _robbo_update_editor_context(self, data, suffix=''):
        payload = dict(data)
        raw_count = payload.pop('max_files_count', None)
        result = original_update(self, payload, suffix=suffix)
        if result.get('success') and raw_count is not None:
            self.max_files_count = max(
                1, min(int(raw_count), ROBBO_ORA_MAX_FILES_COUNT_CAP),
            )
        return result

    OpenAssessmentBlock.update_editor_context = XBlock.json_handler(_robbo_update_editor_context)

    original_get_template = studio_mixin_module.get_template

    def get_template(template_name, using=None):
        override_path = {
            'legacy/edit/oa_edit_basic_settings_list.html': _TEMPLATE_OVERRIDE,
            'legacy/edit/oa_edit_criterion.html': _CRITERION_TEMPLATE_OVERRIDE,
        }.get(template_name)
        if override_path and override_path.is_file():
            engine = engines['django']
            return engine.from_string(override_path.read_text(encoding='utf-8'))
        return original_get_template(template_name, using=using)

    studio_mixin_module.get_template = get_template

    original_studio_view = OpenAssessmentBlock.studio_view

    def studio_view(self, context=None):
        from django.utils import translation

        translation.activate('ru')
        fragment = original_studio_view(self, context)
        fragment.content = _STUDIO_HINT_CSS + fragment.content
        fragment.add_javascript_url(staticfiles_storage.url('js/robbo-ora-studio-patch.js'))
        return fragment

    OpenAssessmentBlock.studio_view = studio_view
    OpenAssessmentBlock._robbo_studio_editor_patched = True


_ORA_TEMPLATE_OVERRIDES = {
    'legacy/oa_uploaded_file.html': _UPLOADED_FILE_TEMPLATE_OVERRIDE,
    'legacy/response/oa_response.html': _RESPONSE_TEMPLATE_OVERRIDE,
}


def _robbo_ora_template_override(template_name):
    override_path = _ORA_TEMPLATE_OVERRIDES.get(template_name)
    if override_path and override_path.is_file():
        from django.template import engines

        return engines['django'].from_string(override_path.read_text(encoding='utf-8'))
    return None


def _patch_ora_template_loader():
    """Override ORA templates for render_assessment and {% include %}."""
    import django.template.loader as template_loader
    import openassessment.xblock.openassessmentblock as oa_block_module

    if getattr(template_loader, '_robbo_ora_template_loader_patched', False):
        return

    original_get_template = template_loader.get_template

    def robbo_get_template(template_name, using=None):
        override = _robbo_ora_template_override(template_name)
        if override is not None:
            return override
        return original_get_template(template_name, using=using)

    template_loader.get_template = robbo_get_template
    oa_block_module.get_template = robbo_get_template
    template_loader._robbo_ora_template_loader_patched = True


def _wrap_ora_learner_fragment(original_view, max_bytes, max_mb, patch_js_path):
    """Inject upload limit, JS patch, and Russian locale into LMS/Studio ORA shell."""
    from django.contrib.staticfiles.storage import staticfiles_storage
    from django.utils import translation

    def wrapped_view(self, context=None):
        translation.activate('ru')
        fragment = original_view(self, context)
        inline = (
            f'<script>window.ROBBO_ORA_MAX_FILE_BYTES={max_bytes};'
            f'window.ROBBO_ORA_MAX_FILE_MB={max_mb};</script>'
        )
        fragment.content = inline + fragment.content
        if patch_js_path.is_file():
            fragment.add_javascript(patch_js_path.read_text(encoding='utf-8'))
        else:
            fragment.add_javascript_url(staticfiles_storage.url('js/robbo-ora-lms-patch.js'))
        return fragment

    return wrapped_view


def patch_ora_student_view():
    """Learner view (LMS + Studio preview): upload limit, JS patch, template overrides."""
    from openassessment.xblock.openassessmentblock import OpenAssessmentBlock
    from webob.response import Response

    if getattr(OpenAssessmentBlock, '_robbo_ora_student_view_patched', False):
        return

    patch_ora_runtime_limits()
    _patch_ora_template_loader()

    max_bytes = _robbo_ora_max_file_upload_bytes()
    max_mb = max_bytes // (1000 * 1000)

    _patch_js_path = Path(__file__).resolve().parents[3] / 'lms' / 'static' / 'js' / 'robbo-ora-lms-patch.js'

    original_student_view = OpenAssessmentBlock.student_view
    original_author_view = OpenAssessmentBlock.author_view
    original_render_assessment = OpenAssessmentBlock.render_assessment

    def render_assessment(self, path, context_dict=None):
        """Render ORA step HTML with Russian locale and file-picker styles."""
        from django.utils import translation

        from .robbo_ora_i18n import ROBBO_ORA_FILE_PICKER_CSS

        translation.activate('ru')
        response = original_render_assessment(self, path, context_dict)
        if (
            path
            and 'legacy/response/oa_response' in path
            and ROBBO_ORA_FILE_PICKER_CSS
            and 'robbo-ora-file-picker' in response.text
        ):
            styled = f'<style type="text/css">{ROBBO_ORA_FILE_PICKER_CSS}</style>{response.text}'
            charset = response.charset or 'utf-8'
            return Response(
                body=styled.encode(charset),
                content_type=response.content_type,
                charset=charset,
            )
        return response

    OpenAssessmentBlock.student_view = _wrap_ora_learner_fragment(
        original_student_view, max_bytes, max_mb, _patch_js_path,
    )
    OpenAssessmentBlock.author_view = _wrap_ora_learner_fragment(
        original_author_view, max_bytes, max_mb, _patch_js_path,
    )
    OpenAssessmentBlock.render_assessment = render_assessment
    OpenAssessmentBlock._robbo_ora_student_view_patched = True


# Backward-compatible alias (LMS app imports this name).
patch_ora_lms_student_view = patch_ora_student_view
