# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-05-16 14:59
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('custom_user', '0004_auto_20170516_2021'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='loyalty_started',
            field=models.DateField(blank=True, null=True, verbose_name='\u0414\u0430\u0442\u0430 \u043d\u0430\u0447\u0430\u043b\u0430 \u043f\u0440\u043e\u0433\u0440\u0430\u043c\u043c\u044b \u043b\u043e\u044f\u043b\u044c\u043d\u043e\u0441\u0442\u0438'),
        ),
    ]