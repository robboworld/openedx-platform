# Copyright (C) 2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution. See NOTICE at repository root.

"""
«Настроить задачи» in the settings of a unit, subsection, section or the whole course (course outline
sidebar of frontend-app-authoring): applies problem settings to every problem inside at once.

GET returns how many problems there are; POST applies the settings given in the JSON body, each one
only when present:

- shuffle: "off" | "per_student" | "every_attempt" — the «Перемешивать варианты ответа» modes of the
  problem editor (ShuffleCard): shuffle="true" on the choice groups of single and multiple choice
  problems plus the randomization that decides when the order is drawn. Problems with a Python script
  (randomization is theirs) or an answer pool (CAPA refuses it together with shuffle) are left out.
- max_attempts: "unlimited" | number
- showanswer: one of SHOWANSWER, with attempts_before_showanswer_button for "after_attempts"
- show_reset_button: true | false
- submission_wait_seconds: number

Each problem goes through the regular Studio save. A published problem without unpublished edits is
republished (like robbo_group_access), so learners get the change at once; in a problem with
unpublished edits the change joins the draft, so the bulk change never publishes someone's work.
"""

import json
import logging
import re

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404
from django.views.decorators.http import require_http_methods
from lxml import etree
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import UsageKey

from common.djangoapps.student.auth import has_studio_write_access
from common.djangoapps.util.json_request import JsonResponse
from xmodule.capa_block import RANDOMIZATION, SHOWANSWER
from xmodule.modulestore.django import modulestore

from .xblock_storage_handlers.view_handlers import _save_xblock

log = logging.getLogger(__name__)

CONTAINER_TYPES = ('course', 'chapter', 'sequential', 'vertical')
SHUFFLE_RANDOMIZATION = {
    'off': None,  # back to the course default
    'per_student': RANDOMIZATION.PER_STUDENT,
    'every_attempt': RANDOMIZATION.ALWAYS,
}
SHOWANSWER_VALUES = {value for name, value in vars(SHOWANSWER).items() if name.isupper()}
CHOICE_GROUPS_XPATH = '//multiplechoiceresponse/choicegroup | //choiceresponse/checkboxgroup | //choiceresponse/radiogroup'
GROUP_TAG = re.compile(r'<(choicegroup|checkboxgroup|radiogroup)\b([^>]*?)(/?)>')
SHUFFLE_ATTRIBUTE = re.compile(r'''\s+shuffle\s*=\s*("[^"]*"|'[^']*')''')

CHOICE = 'choice'
SKIPPED = 'skipped'


class InvalidSettings(ValueError):
    pass


def _problems(block):
    if block.category == 'problem':
        yield block
    elif block.has_children:
        for child in block.get_children():
            yield from _problems(child)


def _choice_kind(problem):
    """
    CHOICE for a single or multiple choice problem whose choices can be shuffled, SKIPPED for one that
    has choices but a Python script or an answer pool, None for any other problem.
    """
    try:
        tree = etree.XML((problem.data or '').encode('utf-8'))
    except etree.XMLSyntaxError:
        return None
    groups = tree.xpath(CHOICE_GROUPS_XPATH)
    if not groups:
        return None
    if tree.xpath('//script') or any(group.get('answer-pool') is not None for group in groups):
        return SKIPPED
    return CHOICE


def _with_shuffle(data, shuffle):
    """
    The OLX with shuffle="true" set on (or removed from) every choice group; only the opening tags
    change, the rest of the OLX stays as the author wrote it.
    """
    def replace(match):
        attributes = SHUFFLE_ATTRIBUTE.sub('', match.group(2))
        return '<{}{}{}{}>'.format(match.group(1), attributes, ' shuffle="true"' if shuffle else '', match.group(3))
    return GROUP_TAG.sub(replace, data)


def _number(value, minimum):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise InvalidSettings(value)
    return value


def _parse(body):
    """
    The requested settings as (shuffle mode or None, metadata dict, nullout list).
    """
    settings = json.loads(body or '{}')
    if not isinstance(settings, dict):
        raise InvalidSettings(settings)
    shuffle = settings.get('shuffle')
    if shuffle is not None and shuffle not in SHUFFLE_RANDOMIZATION:
        raise InvalidSettings(shuffle)
    metadata, nullout = {}, []
    if 'max_attempts' in settings:
        if settings['max_attempts'] == 'unlimited':
            nullout.append('max_attempts')  # unlimited even where the course has a default
        else:
            metadata['max_attempts'] = _number(settings['max_attempts'], 1)
    if 'showanswer' in settings:
        if settings['showanswer'] not in SHOWANSWER_VALUES:
            raise InvalidSettings(settings['showanswer'])
        metadata['showanswer'] = settings['showanswer']
        if settings['showanswer'] == SHOWANSWER.AFTER_SOME_NUMBER_OF_ATTEMPTS:
            metadata['attempts_before_showanswer_button'] = _number(
                settings.get('attempts_before_showanswer_button'), 1,
            )
    if 'show_reset_button' in settings:
        if not isinstance(settings['show_reset_button'], bool):
            raise InvalidSettings(settings['show_reset_button'])
        metadata['show_reset_button'] = settings['show_reset_button']
    if 'submission_wait_seconds' in settings:
        metadata['submission_wait_seconds'] = _number(settings['submission_wait_seconds'], 0)
    return shuffle, metadata, nullout


def _changes(problem, shuffle, metadata, nullout):
    """
    What has to change in this problem: (new OLX or None, metadata, nullout), leaving out what already
    holds, so that a problem that is already set up is not saved again.
    """
    data = None
    metadata = dict(metadata)
    if shuffle is not None and _choice_kind(problem) == CHOICE:
        new_data = _with_shuffle(problem.data, shuffle != 'off')
        if new_data != problem.data:
            data = new_data
        metadata['rerandomize'] = SHUFFLE_RANDOMIZATION[shuffle]
    for name, value in list(metadata.items()):
        field = problem.fields[name]
        if value is None:
            if not field.is_set_on(problem):
                del metadata[name]
        elif field.is_set_on(problem) and field.read_from(problem) == value:
            del metadata[name]
    nullout = [
        name for name in nullout
        if not (problem.fields[name].is_set_on(problem) and getattr(problem, name) is None)
    ]
    return data, metadata, nullout


def _summary(container):
    problems = list(_problems(container))
    kinds = [_choice_kind(problem) for problem in problems]
    return {
        'problems': len(problems),
        'choice_problems': kinds.count(CHOICE),
        'skipped_choice_problems': kinds.count(SKIPPED),
    }


# Not atomic, like the xblock handler: publishing starts async tasks that must see the changes.
@transaction.non_atomic_requests
@require_http_methods(['GET', 'POST'])
@login_required
def problem_settings(request, usage_key_string):
    try:
        usage_key = UsageKey.from_string(usage_key_string)
    except InvalidKeyError as exc:
        raise Http404 from exc
    if usage_key.block_type not in CONTAINER_TYPES:
        return JsonResponse({'error': 'Problem settings apply to a unit, subsection, section or course.'}, 400)
    if not has_studio_write_access(request.user, usage_key.course_key):
        raise PermissionDenied()

    store = modulestore()
    if request.method == 'GET':
        with store.bulk_operations(usage_key.course_key):
            return JsonResponse(_summary(store.get_item(usage_key, depth=None)))

    try:
        shuffle, metadata, nullout = _parse(request.body)
    except (InvalidSettings, ValueError) as exc:
        return JsonResponse({'error': f'Invalid problem settings: {exc}'}, 400)

    changed = 0
    with store.bulk_operations(usage_key.course_key):
        container = store.get_item(usage_key, depth=None)
        for problem in list(_problems(container)):
            data, problem_metadata, problem_nullout = _changes(problem, shuffle, metadata, nullout)
            if data is None and not problem_metadata and not problem_nullout:
                continue
            _save_xblock(
                request.user, problem, data=data, metadata=problem_metadata, nullout=problem_nullout or None,
                publish=None if store.has_changes(problem) else 'republish',
            )
            changed += 1
        summary = _summary(store.get_item(usage_key, depth=None))
    log.info('robbo: %s applied problem settings to %s problems in %s', request.user.username, changed, usage_key)
    return JsonResponse({'changed': changed, **summary})
