# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-08-01 17:40
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('callcenter', '0002_auto_20161229_0023'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='managercallrequest',
            name='subject',
        ),
        migrations.AddField(
            model_name='managercallrequest',
            name='phone',
            field=models.CharField(blank=True, max_length=12, null=True, verbose_name='\u0442\u0435\u043b\u0435\u0444\u043e\u043d'),
        ),
    ]
