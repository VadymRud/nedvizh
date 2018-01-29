# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-06-16 11:46
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('custom_user', '0006_user_gender'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='gender',
            field=models.CharField(blank=True, choices=[(None, '\u041d\u0435 \u043e\u043f\u0440\u0435\u0434\u0435\u043b\u0435\u043d'), (b'male', '\u041c\u0443\u0436\u0441\u043a\u043e\u0439'), (b'female', '\u0416\u0435\u043d\u0441\u043a\u0438\u0439')], max_length=6, null=True, verbose_name='\u043f\u043e\u043b'),
        ),
    ]
