# -*- coding: utf-8 -*-
# Generated by Django 1.9.10 on 2017-03-17 12:29
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ad', '0005_ad_is_sold'),
    ]

    operations = [
        migrations.AddField(
            model_name='viewscount',
            name='is_fake',
            field=models.BooleanField(default=False, verbose_name='\u0444\u044d\u0439\u043a\u043e\u0432\u044b\u0435 \u043f\u0440\u043e\u0441\u043c\u043e\u0442\u0440\u044b?'),
        ),
    ]