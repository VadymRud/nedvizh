# -*- coding: utf-8 -*-
# Generated by Django 1.9.10 on 2017-04-05 13:28
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('newhome', '0004_layoutnameoption'),
    ]

    operations = [
        migrations.AlterField(
            model_name='newhome',
            name='region',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='newhomes', to='ad.Region', verbose_name='\u043f\u0440\u0438\u0441\u0432\u043e\u0435\u043d\u043d\u044b\u0439 \u0440\u0435\u0433\u0438\u043e\u043d'),
        ),
    ]
