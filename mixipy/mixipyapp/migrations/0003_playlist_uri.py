# Generated by Django 3.1.5 on 2021-01-08 21:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mixipyapp', '0002_request_log_pub_date'),
    ]

    operations = [
        migrations.AddField(
            model_name='playlist',
            name='uri',
            field=models.CharField(default='test', max_length=50),
            preserve_default=False,
        ),
    ]
