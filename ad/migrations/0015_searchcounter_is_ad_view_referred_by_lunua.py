# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-07-20 21:29
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ad', '0014_auto_20170630_1733'),
    ]

    operations = [
        migrations.AddField(
            model_name='searchcounter',
            name='is_ad_view_referred_by_lunua',
            field=models.BooleanField(default=False, verbose_name='\u043f\u0440\u043e\u0441\u043c\u043e\u0442\u0440 \u043e\u0431\u044a\u044f\u0432\u043b\u0435\u043d\u0438\u044f \u043f\u0440\u0438 \u043f\u0435\u0440\u0435\u0445\u043e\u0434\u0435 \u0441 lun.ua?'),
        ),
    ]
