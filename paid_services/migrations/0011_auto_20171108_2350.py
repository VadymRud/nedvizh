# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-11-08 23:50
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('paid_services', '0010_vipplacement_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='vipplacement',
            name='days',
            field=models.PositiveIntegerField(default=7, verbose_name='\u0441\u0440\u043e\u043a, \u0434\u043d\u0435\u0439'),
        ),
    ]
