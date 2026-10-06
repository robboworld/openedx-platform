# Copyright (C) 2024-2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only

"""Robbo ORA: per-block file count/size limits and Studio template overrides."""

import json
from pathlib import Path

from django.conf import settings
from django.utils import translation
from voluptuous import Optional, Schema
from xblock.fields import Boolean, Dict, Integer, Scope

from xmodule.course_metadata_utils import is_russian_language

ROBBO_ORA_DEFAULT_MAX_FILES_COUNT = getattr(settings, 'ROBBO_ORA_DEFAULT_MAX_FILES_COUNT', 1)
ROBBO_ORA_MAX_FILES_COUNT_CAP = getattr(settings, 'ROBBO_ORA_MAX_FILES_COUNT_CAP', 20)
ROBBO_ORA_DEFAULT_MAX_FILE_BYTES = 5 * 1000 * 1000  # 5 MB
# "Larger files" option: per-extension limit in MB, 1..cap. Keep in sync with the LMS Caddy limit for
# /openassessment/fileupload/* (tutor-plugin-robbo-mfe-branding, caddyfile-lms patch).
ROBBO_ORA_LARGE_FILE_MB_CAP = getattr(settings, 'ROBBO_ORA_LARGE_FILE_MB_CAP', 50)


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
#openassessment_validation_alert.covered {
    display: none !important;
}
#openassessment_validation_alert:not(.covered) {
    display: block !important;
}
#openassessment-editor .robbo-ora-necessity-hint {
    color: #8f2f1f !important;
    font-weight: 600;
    margin-top: 0.5em;
}
#openassessment-editor .robbo-ora-necessity-hint.is--visible {
    display: block !important;
}
#openassessment-editor .robbo-ora-necessity-hint.is--hidden {
    display: none !important;
}
#openassessment-editor .robbo-ora-large-files {
    margin-top: 16px;
}
#openassessment-editor .robbo-ora-large-files__toggle {
    display: flex;
    align-items: center;
    gap: 10px;
}
#openassessment-editor .robbo-ora-large-files__toggle label.setting-label {
    width: auto;
    margin: 0;
    cursor: pointer;
}
/* Studio stretches every settings input to 45% width; keep the checkbox at its natural size. */
#openassessment-editor .robbo-ora-large-files__toggle input.robbo-ora-large-files__checkbox {
    flex: 0 0 auto;
    width: 18px;
    min-width: 0;
    height: 18px;
    margin: 0;
    padding: 0;
    accent-color: #00af41;
    cursor: pointer;
}
#openassessment-editor .robbo-ora-size-limits.is--hidden,
#openassessment-editor .robbo-ora-size-limits__empty.is--hidden {
    display: none;
}
#openassessment-editor .robbo-ora-size-limits__title {
    display: block;
    width: auto;
    margin: 8px 0;
}
#openassessment-editor .robbo-ora-size-limits__list {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 8px 24px;
    margin: 0 0 8px;
    padding: 0;
    list-style: none;
}
#openassessment-editor .robbo-ora-size-limits__row {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 0;
}
#openassessment-editor .robbo-ora-size-limits__row label {
    min-width: 64px;
    color: #383838;
    font-weight: 600;
}
#openassessment-editor .robbo-ora-size-limits__row input.setting-input {
    width: 72px;
    min-width: 0;
    text-align: right;
}
#openassessment-editor .robbo-ora-size-limits__row input.is--invalid {
    border-color: #c23c2a;
}
</style>
"""

# ORA {% include %} uses django.template.loader, not studio_mixin.get_template.
_NECESSITY_LABELS_INLINE_JS = """
<script type="text/javascript">
(function () {
  var EN = { required: 'Required', optional: 'Optional', '': 'None' };
  var RU = { required: 'Обязательно', optional: 'Необязательно', '': 'Нет' };
  function syncNecessityLabels() {
    ['openassessment_submission_text_response', 'openassessment_submission_file_upload_response'].forEach(
      function (id) {
        var el = document.getElementById(id);
        if (!el) {
          return;
        }
        var lang = (el.getAttribute('data-robbo-ora-ui-lang') || '').toLowerCase();
        var labels = lang.indexOf('ru') === 0 ? RU : EN;
        Array.prototype.forEach.call(el.options, function (opt) {
          if (Object.prototype.hasOwnProperty.call(labels, opt.value) && opt.textContent !== labels[opt.value]) {
            opt.textContent = labels[opt.value];
          }
        });
      },
    );
  }
  // One pass, no MutationObserver: the label writes retriggered it endlessly and froze Studio.
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', syncNecessityLabels);
  } else {
    syncNecessityLabels();
  }
})();
</script>
"""


def _effective_max_files_count(block):
    count = getattr(block, 'max_files_count', None)
    if not count or count < 1:
        count = ROBBO_ORA_DEFAULT_MAX_FILES_COUNT
    return min(int(count), ROBBO_ORA_MAX_FILES_COUNT_CAP)


def _default_file_mb():
    return max(1, _robbo_ora_max_file_upload_bytes() // (1000 * 1000))


def _allowed_extensions(block):
    """Extensions the learner may upload (preset list for image / pdf-and-image, else the custom list)."""
    getter = getattr(block, 'get_allowed_file_types_or_preset', None)
    extensions = getter() if getter else None
    return [str(ext).strip().strip('.').lower() for ext in (extensions or []) if str(ext).strip()]


def _normalize_size_limits(raw):
    """{ext: MB} with lower-case extensions and MB clamped to 1..ROBBO_ORA_LARGE_FILE_MB_CAP."""
    limits = {}
    for ext, value in (raw or {}).items():
        ext = str(ext).strip().strip('.').lower()
        try:
            mb = int(value)
        except (TypeError, ValueError):
            continue
        if ext:
            limits[ext] = max(1, min(mb, ROBBO_ORA_LARGE_FILE_MB_CAP))
    return limits


def _file_size_limits_mb(block):
    """
    Per-extension limits shown to learners and enforced in robbo-ora-lms-patch.js.

    Empty dict when the "larger files" option is off: then the global STUDENT_FILEUPLOAD_MAX_SIZE applies.
    """
    if not getattr(block, 'robbo_large_files', False):
        return {}
    saved = _normalize_size_limits(getattr(block, 'robbo_file_size_limits', None))
    default_mb = _default_file_mb()
    return {ext: saved.get(ext, default_mb) for ext in _allowed_extensions(block)}


def _group_size_limits(size_limits):
    """[('jpg, pdf, png', 5), ...]: one row per size, largest first, extensions alphabetical within a row."""
    groups = {}
    for ext, mb in size_limits.items():
        groups.setdefault(mb, []).append(ext)
    return [(', '.join(sorted(exts)), mb) for mb, exts in sorted(groups.items(), reverse=True)]


def _learner_max_files_count(block):
    """File limit shown to the learner: 1 when multiple files are not allowed."""
    if not getattr(block, 'allow_multiple_files', True):
        return 1
    return _effective_max_files_count(block)


class _RobboOraFilesLimitMixin:
    """Mixin registered at runtime so max_files_count gets a proper field name."""

    max_files_count = Integer(
        display_name='Maximum File Uploads',
        default=ROBBO_ORA_DEFAULT_MAX_FILES_COUNT,
        scope=Scope.settings,
    )
    robbo_large_files = Boolean(
        display_name='Larger file sizes',
        default=False,
        scope=Scope.settings,
    )
    robbo_file_size_limits = Dict(
        display_name='Maximum file size per extension, MB',
        default={},
        scope=Scope.settings,
    )


def _register_max_files_count_field(open_assessment_block):
    """
    Register max_files_count via mixin.

    Assigning Integer() into fields{} at runtime leaves field.name='unknown' and
    breaks LMS staff preview (KeyError in add_staff_markup).
    """
    for field_name in ('max_files_count', 'robbo_large_files', 'robbo_file_size_limits'):
        existing = open_assessment_block.fields.get(field_name)
        if existing is not None and getattr(existing, 'name', None) == 'unknown':
            del open_assessment_block.fields[field_name]

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
    from django.template.loader import get_template as django_get_template

    if getattr(OpenAssessmentBlock, '_robbo_studio_editor_patched', False):
        return

    patch_ora_runtime_limits()
    _patch_ora_template_loader()

    schema_dict = dict(schema_module.EDITOR_UPDATE_SCHEMA.schema)
    schema_dict[Optional('max_files_count')] = int
    schema_dict[Optional('robbo_large_files')] = bool
    schema_dict[Optional('robbo_file_size_limits')] = dict
    updated_schema = Schema(schema_dict)
    # studio_mixin imports EDITOR_UPDATE_SCHEMA at load time; patch both bindings.
    schema_module.EDITOR_UPDATE_SCHEMA = updated_schema
    studio_mixin_module.EDITOR_UPDATE_SCHEMA = updated_schema

    original_editor_context = OpenAssessmentBlock.editor_context

    def editor_context(self):
        from .robbo_ora_defaults import (
            ROBBO_ORA_NECESSITY_OPTIONS_EN,
            ROBBO_ORA_NECESSITY_OPTIONS_RU,
        )
        from .robbo_ora_i18n import effective_ora_ui_language, get_robbo_ora_runtime_catalog

        context = original_editor_context(self)
        context['max_files_count'] = _effective_max_files_count(self)
        max_upload_mb = _robbo_ora_max_file_upload_bytes() // (1000 * 1000)
        context['max_upload_mb'] = max_upload_mb
        ui_lang = effective_ora_ui_language()
        context['robbo_ora_ui_language'] = ui_lang
        context['robbo_ora_studio_english'] = not is_russian_language(ui_lang)
        if is_russian_language(ui_lang):
            context['necessity_options'] = dict(ROBBO_ORA_NECESSITY_OPTIONS_RU)
        else:
            context['necessity_options'] = dict(ROBBO_ORA_NECESSITY_OPTIONS_EN)
        catalog = get_robbo_ora_runtime_catalog()
        context['file_upload_max_size_help'] = catalog[
            'By default each file may be up to %(max_mb)s MB. Turn on "Larger file sizes" to set a limit '
            'for each file type (up to %(cap_mb)s MB).'
        ] % {'max_mb': max_upload_mb, 'cap_mb': ROBBO_ORA_LARGE_FILE_MB_CAP}
        context['robbo_large_files'] = bool(getattr(self, 'robbo_large_files', False))
        context['robbo_default_file_mb'] = _default_file_mb()
        context['robbo_large_file_mb_cap'] = ROBBO_ORA_LARGE_FILE_MB_CAP
        context['robbo_file_size_limits_json'] = json.dumps(
            _normalize_size_limits(getattr(self, 'robbo_file_size_limits', None)),
        )
        context['robbo_preset_extensions_json'] = json.dumps({
            'image': list(self.ALLOWED_IMAGE_EXTENSIONS),
            'pdf-and-image': list(self.ALLOWED_FILE_EXTENSIONS),
        })
        context['file_upload_description_help'] = catalog[
            'Learners may leave file descriptions empty; a dash is saved when no description is provided.'
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
        raw_large_files = payload.pop('robbo_large_files', None)
        raw_size_limits = payload.pop('robbo_file_size_limits', None)
        result = original_update(self, payload, suffix=suffix)
        if result.get('success'):
            if raw_count is not None:
                try:
                    count = int(raw_count)
                except (TypeError, ValueError):
                    count = ROBBO_ORA_DEFAULT_MAX_FILES_COUNT
                self.max_files_count = max(
                    1, min(count, ROBBO_ORA_MAX_FILES_COUNT_CAP),
                )
            if raw_large_files is not None:
                self.robbo_large_files = bool(raw_large_files)
            if raw_size_limits is not None:
                self.robbo_file_size_limits = _normalize_size_limits(raw_size_limits)
        return result

    OpenAssessmentBlock.update_editor_context = XBlock.json_handler(_robbo_update_editor_context)

    def get_template(template_name, using=None):
        return django_get_template(template_name, using=using)

    studio_mixin_module.get_template = get_template

    original_studio_view = OpenAssessmentBlock.studio_view

    def studio_view(self, context=None):
        from .robbo_ora_i18n import effective_ora_ui_language

        ui_lang = effective_ora_ui_language()
        if is_russian_language(ui_lang):
            translation.activate('ru')
        elif ui_lang:
            translation.activate(ui_lang)
        fragment = original_studio_view(self, context)
        fragment.content = (
            _STUDIO_HINT_CSS + fragment.content + _NECESSITY_LABELS_INLINE_JS
        )
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


def _robbo_ora_settings_list_template():
    if not _TEMPLATE_OVERRIDE.is_file():
        return None
    from django.template import engines

    return engines['django'].from_string(_TEMPLATE_OVERRIDE.read_text(encoding='utf-8'))


def _patch_ora_template_loader():
    """Override ORA templates for Studio {% include %} and LMS render_assessment."""
    import django.template.loader as template_loader
    import openassessment.xblock.openassessmentblock as oa_block_module

    if getattr(template_loader, '_robbo_ora_template_loader_patched', False):
        return

    original_get_template = template_loader.get_template

    def robbo_get_template(template_name, using=None):
        if template_name == 'legacy/edit/oa_edit_basic_settings_list.html':
            settings_tpl = _robbo_ora_settings_list_template()
            if settings_tpl is not None:
                return settings_tpl
        from .robbo_ora_i18n import effective_ora_ui_language

        ui_lang = effective_ora_ui_language()
        if is_russian_language(ui_lang):
            override = _robbo_ora_template_override(template_name)
            if override is not None:
                return override
            if template_name == 'legacy/edit/oa_edit_criterion.html' and _CRITERION_TEMPLATE_OVERRIDE.is_file():
                from django.template import engines

                return engines['django'].from_string(
                    _CRITERION_TEMPLATE_OVERRIDE.read_text(encoding='utf-8'),
                )
        return original_get_template(template_name, using=using)

    template_loader.get_template = robbo_get_template
    oa_block_module.get_template = robbo_get_template
    template_loader._robbo_ora_template_loader_patched = True


def _wrap_ora_learner_fragment(original_view, max_bytes, max_mb, patch_js_path):
    """Inject upload limit, JS patch, and optional Russian locale into LMS/Studio ORA shell."""
    from django.contrib.staticfiles.storage import staticfiles_storage

    def wrapped_view(self, context=None):
        from .robbo_ora_i18n import ROBBO_ORA_RESPONSE_STEP_CSS

        if is_russian_language(translation.get_language()):
            translation.activate('ru')
        fragment = original_view(self, context)
        inline = (
            f'<script>window.ROBBO_ORA_MAX_FILE_BYTES={max_bytes};'
            f'window.ROBBO_ORA_MAX_FILE_MB={max_mb};</script>'
            f'<style type="text/css">{ROBBO_ORA_RESPONSE_STEP_CSS}</style>'
        )
        fragment.content = inline + fragment.content
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
        """Render ORA step HTML with Russian locale, upload limits and response-step styles."""
        from .robbo_ora_i18n import ROBBO_ORA_RESPONSE_STEP_CSS

        if is_russian_language(translation.get_language()):
            translation.activate('ru')
        is_response_step = bool(path and 'legacy/response/oa_response' in path)
        if is_response_step:
            context_dict = dict(context_dict or {})
            learner_max_files = _learner_max_files_count(self)
            context_dict['robbo_max_files_count'] = learner_max_files
            # Singular picker/button labels and no `multiple` when only one file fits.
            context_dict['robbo_multiple_files'] = learner_max_files > 1
            # {% include %} resolves names through the Django engine loaders, not the patched
            # get_template(), so hand the override over as a template object.
            context_dict['robbo_uploaded_file_template'] = _robbo_ora_template_override(
                'legacy/oa_uploaded_file.html',
            )
            context_dict['robbo_max_file_mb'] = max_mb
            size_limits = _file_size_limits_mb(self)
            context_dict['robbo_file_size_limits'] = _group_size_limits(size_limits)
            context_dict['robbo_file_size_limits_json'] = json.dumps(size_limits)
        response = original_render_assessment(self, path, context_dict)
        if is_response_step and ROBBO_ORA_RESPONSE_STEP_CSS:
            styled = f'<style type="text/css">{ROBBO_ORA_RESPONSE_STEP_CSS}</style>{response.text}'
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
