# Generated by Django 3.1.5 on 2021-01-09 07:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mixipyapp', '0009_page_title'),
    ]

    operations = [
        migrations.AddField(
            model_name='request_log',
            name='title',
            field=models.CharField(blank=True, max_length=100),
        ),
    ]
