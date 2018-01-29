# -*- coding: utf-8 -*-
# Generated by Django 1.9.10 on 2017-01-19 16:29
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('newhome', '0002_auto_20170117_1155'),
    ]

    operations = [
        migrations.AlterField(
            model_name='newhome',
            name='parking_info',
            field=models.CharField(choices=[(b'underground', '\u043f\u043e\u0434\u0437\u0435\u043c\u043d\u044b\u0439'), (b'ground', '\u043d\u0430\u0437\u0435\u043c\u043d\u044b\u0439'), (b'for_guests', '\u0433\u043e\u0441\u0442\u0435\u0432\u043e\u0439'), (b'none', '\u043e\u0442\u0441\u0443\u0442\u0441\u0442\u0432\u0443\u0435\u0442')], default='none', max_length=255, verbose_name='\u043f\u0430\u0440\u043a\u0438\u043d\u0433'),
        ),
        migrations.AlterField(
            model_name='newhome',
            name='walls',
            field=models.CharField(blank=True, choices=[(b'wall01', '\u043a\u0438\u0440\u043f\u0438\u0447'), (b'wall02', '\u043b\u0435\u0433\u043a\u043e\u0431\u0435\u0442\u043e\u043d\u043d\u044b\u0435 \u0431\u043b\u043e\u043a\u0438'), (b'wall03', '\u043a\u0435\u0440\u0430\u043c\u043e\u0431\u043b\u043e\u043a'), (b'wall04', '\u0435\u0441\u0442\u0435\u0441\u0442\u0432\u0435\u043d\u043d\u044b\u0439 \u043a\u0430\u043c\u0435\u043d\u044c'), (b'wall05', '\u0434\u0435\u0440\u0435\u0432\u043e'), (b'wall06', '\u0436\u0435\u043b\u0435\u0437\u043e\u0431\u0435\u0442\u043e\u043d')], max_length=255, verbose_name='\u0441\u0442\u0435\u043d\u044b'),
        ),
    ]
