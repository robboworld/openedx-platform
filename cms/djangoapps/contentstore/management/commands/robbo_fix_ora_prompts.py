"""
Replace upstream ORA sample content with Robbo Russian defaults.
"""
# Modifications Copyright (C) 2026 Robbo. See NOTICE at repository root.

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from xmodule.modulestore.django import modulestore

from cms.djangoapps.contentstore.robbo_ora_defaults import (
    apply_russian_ora_content,
    should_replace_ora_prompt,
    should_replace_ora_rubric,
    should_replace_ora_title,
)


class Command(BaseCommand):
    help = 'Replace upstream ORA sample prompts, rubric, and title with Robbo Russian defaults.'

    def add_arguments(self, parser):
        parser.add_argument('course_id', help='Course key, e.g. course-v1:ORG+COURSE+RUN')
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Only report blocks that would be updated.',
        )

    def handle(self, *args, **options):
        try:
            course_key = CourseKey.from_string(options['course_id'])
        except InvalidKeyError as exc:
            raise CommandError(f'Invalid course id: {options["course_id"]}') from exc

        user = get_user_model().objects.filter(is_staff=True).order_by('id').first()
        if user is None:
            raise CommandError('No staff user found to attribute modulestore updates.')

        store = modulestore()
        updated = 0
        scanned = 0

        with store.bulk_operations(course_key):
            for block in store.get_items(course_key, qualifiers={'category': 'openassessment'}):
                scanned += 1
                needs_update = (
                    should_replace_ora_prompt(block.prompts)
                    or should_replace_ora_title(block.title)
                    or should_replace_ora_rubric(block.rubric_criteria)
                )
                if not needs_update:
                    continue
                self.stdout.write(f'update {block.location}')
                if options['dry_run']:
                    updated += 1
                    continue
                apply_russian_ora_content(block)
                store.update_item(block, user.id)
                updated += 1

        suffix = ' (dry run)' if options['dry_run'] else ''
        self.stdout.write(
            self.style.SUCCESS(
                f'Scanned {scanned} ORA block(s); updated {updated}{suffix}.'
            )
        )
