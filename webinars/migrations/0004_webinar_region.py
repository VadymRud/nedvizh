# -*- coding: utf-8 -*-
# Generated by Django 1.9.10 on 2017-02-16 15:28
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ad', '0004_auto_20170112_0310'),
        ('webinars', '0003_webinar_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='webinar',
            name='region',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='ad.Region', verbose_name='\u0420\u0435\u0433\u0438\u043e\u043d'),
        ),
    ]
