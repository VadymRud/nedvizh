# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-04-26 14:19
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('profile', '0006_manager'),
    ]

    operations = [
        migrations.AddField(
            model_name='manager',
            name='is_available_for_new_users',
            field=models.BooleanField(default=True, verbose_name='\u0438\u0441\u043f\u043e\u043b\u044c\u0437\u0443\u0435\u0442\u0441\u044f \u0434\u043b\u044f \u043d\u043e\u0432\u044b\u0445 \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u0435\u0439'),
        ),
    ]
