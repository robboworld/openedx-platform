"""
Xblock services for creating xblocks.
"""
# Modifications Copyright (C) 2026 Robbo. See NOTICE at repository root.

from uuid import uuid4

from django.utils import translation
from django.utils.translation import gettext as _
from xmodule.course_metadata_utils import is_russian_language, localized_boilerplate_template_id
from xmodule.modulestore.django import modulestore
from xmodule.tabs import StaticTab

from cms.djangoapps.models.settings.course_grading import CourseGradingModel
from openedx.core.toggles import ENTRANCE_EXAMS

from .xblock_helpers import usage_key_with_run
from ..helpers import GRADER_TYPES, remove_entrance_exam_graders, xblock_type_display_name


def _load_create_template(block_class, template_id):
    """
    Load boilerplate metadata/data, preferring a RU variant when LANGUAGE_CODE is ru.
    """
    if not template_id or block_class is None:
        return None, False

    used_localized = False
    template = None
    if is_russian_language():
        localized_id = localized_boilerplate_template_id(template_id)
        if localized_id != template_id:
            template = block_class.get_template(localized_id)
            used_localized = template is not None
    if template is None:
        template = block_class.get_template(template_id)
    return template, used_localized


def _russian_display_name(name):
    """Translate a display name under the Russian locale catalog."""
    if not name:
        return name
    with translation.override('ru'):
        return _(name)


def create_xblock(parent_locator, user, category, display_name, boilerplate=None, is_entrance_exam=False):
    """
    Performs the actual grunt work of creating items/xblocks -- knows nothing about requests, views, etc.
    """
    store = modulestore()
    usage_key = usage_key_with_run(parent_locator)
    with store.bulk_operations(usage_key.course_key):
        parent = store.get_item(usage_key)
        dest_usage_key = usage_key.replace(category=category, name=uuid4().hex)

        # get the metadata, display_name, and definition from the caller
        metadata = {}
        data = None
        template_id = boilerplate
        used_localized_template = False
        if template_id:
            clz = parent.runtime.load_block_type(category)
            template, used_localized_template = _load_create_template(clz, template_id)
            if template is not None:
                metadata = dict(template.get('metadata', {}) or {})
                data = template.get('data')

        use_ru = is_russian_language()
        if display_name is not None:
            metadata['display_name'] = (
                _russian_display_name(display_name) if use_ru else display_name
            )
        elif use_ru:
            if metadata.get('display_name') and not used_localized_template:
                metadata['display_name'] = _russian_display_name(metadata['display_name'])
            elif not metadata.get('display_name'):
                with translation.override('ru'):
                    localized_name = xblock_type_display_name(category)
                if localized_name:
                    metadata['display_name'] = localized_name

        # We should use the 'fields' kwarg for newer block settings/values (vs. metadata or data)
        fields = {}

        # Entrance Exams: Chapter module positioning
        child_position = None
        if ENTRANCE_EXAMS.is_enabled():
            if category == 'chapter' and is_entrance_exam:
                fields['is_entrance_exam'] = is_entrance_exam
                fields['in_entrance_exam'] = True  # Inherited metadata, all children will have it
                child_position = 0

        # TODO need to fix components that are sending definition_data as strings, instead of as dicts
        # For now, migrate them into dicts here.
        if isinstance(data, str):
            data = {'data': data}

        created_block = store.create_child(
            user.id,
            usage_key,
            dest_usage_key.block_type,
            block_id=dest_usage_key.block_id,
            fields=fields,
            definition_data=data,
            metadata=metadata,
            runtime=parent.runtime,
            position=child_position,
        )

        # Entrance Exams: Grader assignment
        if ENTRANCE_EXAMS.is_enabled():
            course_key = usage_key.course_key
            course = store.get_course(course_key)
            if hasattr(course, 'entrance_exam_enabled') and course.entrance_exam_enabled:
                if category == 'sequential' and parent_locator == course.entrance_exam_id:
                    # Clean up any pre-existing entrance exam graders
                    remove_entrance_exam_graders(course_key, user)
                    grader = {
                        "type": GRADER_TYPES['ENTRANCE_EXAM'],
                        "min_count": 0,
                        "drop_count": 0,
                        "short_label": "Entrance",
                        "weight": 0
                    }
                    grading_model = CourseGradingModel.update_grader_from_json(
                        course.id,
                        grader,
                        user
                    )
                    CourseGradingModel.update_section_grader_type(
                        created_block,
                        grading_model['type'],
                        user
                    )

        # VS[compat] cdodge: This is a hack because static_tabs also have references from the course block, so
        # if we add one then we need to also add it to the policy information (i.e. metadata)
        # we should remove this once we can break this reference from the course to static tabs
        if category == 'static_tab':
            display_name = display_name or _("Empty")  # Prevent name being None
            if use_ru and display_name:
                display_name = _russian_display_name(display_name)
            course = store.get_course(dest_usage_key.course_key)
            course.tabs.append(
                StaticTab(
                    name=display_name,
                    url_slug=dest_usage_key.block_id,
                )
            )
            store.update_item(course, user.id)

        return created_block
