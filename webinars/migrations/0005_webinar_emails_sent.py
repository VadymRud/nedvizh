# -*- coding: utf-8 -*-
# Generated by Django 1.9.10 on 2017-02-16 15:46
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('webinars', '0004_webinar_region'),
    ]

    operations = [
        migrations.AddField(
            model_name='webinar',
            name='emails_sent',
            field=models.PositiveIntegerField(default=0, verbose_name='\u041e\u0442\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u043d\u043e \u043f\u0438\u0441\u0435\u043c'),
        ),
    ]
