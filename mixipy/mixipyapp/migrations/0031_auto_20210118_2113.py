# Generated by Django 3.1.5 on 2021-01-18 21:13

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('mixipyapp', '0030_auto_20210118_2113'),
    ]

    operations = [
        migrations.RenameField(
            model_name='searchquery',
            old_name='keywords',
            new_name='key',
        ),
    ]
