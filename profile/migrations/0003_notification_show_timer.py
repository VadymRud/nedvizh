# -*- coding: utf-8 -*-
# Generated by Django 1.9.10 on 2017-01-25 04:11
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('profile', '0002_auto_20170120_1408'),
    ]

    operations = [
        migrations.AddField(
            model_name='notification',
            name='show_timer',
            field=models.BooleanField(default=False, verbose_name='\u0432\u044b\u0432\u043e\u0434\u0438\u0442\u044c \u0442\u0430\u0439\u043c\u0435\u0440 \u043e\u0431\u0440\u0430\u0442\u043d\u043e\u0433\u043e \u043e\u0442\u0441\u0447\u0435\u0442\u0430'),
        ),
    ]
