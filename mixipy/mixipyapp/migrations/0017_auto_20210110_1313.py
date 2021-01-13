# Generated by Django 3.1.5 on 2021-01-10 13:13

import datetime
from django.db import migrations, models
from django.utils.timezone import utc
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('mixipyapp', '0016_auto_20210110_1302'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='page',
            name='request_log',
        ),
        migrations.AddField(
            model_name='page',
            name='created_datetime',
            field=models.DateTimeField(default=datetime.datetime(2021, 1, 10, 13, 13, 40, 502215, tzinfo=utc)),
        ),
        migrations.AddField(
            model_name='page',
            name='modified_datetime',
            field=models.DateTimeField(blank=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
    ]
