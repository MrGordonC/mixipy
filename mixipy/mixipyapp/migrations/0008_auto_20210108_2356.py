# Generated by Django 3.1.5 on 2021-01-08 23:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mixipyapp', '0007_page_request_log'),
    ]

    operations = [
        migrations.AlterField(
            model_name='request_log',
            name='pub_date',
            field=models.DateTimeField(blank=True),
        ),
    ]
