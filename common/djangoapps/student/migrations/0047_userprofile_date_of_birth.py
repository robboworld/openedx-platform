# Generated manually for Robbo registration date_of_birth

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('student', '0046_alter_userprofile_phone_number'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='date_of_birth',
            field=models.DateField(blank=True, db_index=True, null=True),
        ),
    ]
