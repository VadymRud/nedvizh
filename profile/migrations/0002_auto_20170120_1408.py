# -*- coding: utf-8 -*-
# Generated by Django 1.9.10 on 2017-01-20 14:08
from __future__ import unicode_literals

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('profile', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='messagelist',
            name='filter_user_by_id',
            field=django.contrib.postgres.fields.ArrayField(base_field=models.PositiveIntegerField(), blank=True, null=True, size=None, verbose_name='\u0444\u0438\u043b\u044c\u0442\u0440 \u044e\u0437\u0435\u0440\u043e\u0432 \u043f\u043e ID'),
        ),
        migrations.AddField(
            model_name='notification',
            name='filter_user_by_id',
            field=django.contrib.postgres.fields.ArrayField(base_field=models.PositiveIntegerField(), blank=True, null=True, size=None, verbose_name='\u0444\u0438\u043b\u044c\u0442\u0440 \u044e\u0437\u0435\u0440\u043e\u0432 \u043f\u043e ID'),
        ),
    ]
