# Copyright (C) 2024-2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# Part of the Robbo Open edX distribution (YooKassa checkout). See NOTICE at repository root.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import lms.djangoapps.robbo_payments.models
import opaque_keys.edx.django.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Order',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'order_number',
                    models.CharField(
                        db_index=True,
                        default=lms.djangoapps.robbo_payments.models.generate_order_number,
                        max_length=32,
                        unique=True,
                    ),
                ),
                ('course_key', opaque_keys.edx.django.models.CourseKeyField(db_index=True, max_length=255)),
                ('sku', models.CharField(db_index=True, max_length=255)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('currency', models.CharField(default='RUB', max_length=8)),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('pending', 'Pending'),
                            ('paid', 'Paid'),
                            ('failed', 'Failed'),
                            ('canceled', 'Canceled'),
                            ('refunded', 'Refunded'),
                        ],
                        db_index=True,
                        default='pending',
                        max_length=16,
                    ),
                ),
                ('idempotency_key', models.CharField(max_length=64, unique=True)),
                (
                    'yookassa_payment_id',
                    models.CharField(blank=True, db_index=True, max_length=64, null=True, unique=True),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('paid_at', models.DateTimeField(blank=True, null=True)),
                (
                    'user',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='robbo_payment_orders',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'ordering': ('-created_at',),
            },
        ),
        migrations.CreateModel(
            name='PaymentAttempt',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_type', models.CharField(blank=True, default='', max_length=64)),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('received', 'Received'),
                            ('succeeded', 'Succeeded'),
                            ('canceled', 'Canceled'),
                            ('error', 'Error'),
                        ],
                        default='received',
                        max_length=16,
                    ),
                ),
                ('source_ip', models.GenericIPAddressField(blank=True, null=True)),
                ('payload', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'order',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='payment_attempts',
                        to='robbo_payments.order',
                    ),
                ),
            ],
            options={
                'ordering': ('-created_at',),
            },
        ),
        migrations.AddIndex(
            model_name='order',
            index=models.Index(fields=['user', 'course_key', 'status'], name='robbo_payme_user_id_6f0d0a_idx'),
        ),
    ]
