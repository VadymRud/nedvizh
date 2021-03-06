# -*- coding: utf-8 -*-
# Generated by Django 1.9.10 on 2017-02-15 15:45
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('webinars', '0002_auto_20170127_1007'),
    ]

    operations = [
        migrations.AddField(
            model_name='webinar',
            name='status',
            field=models.CharField(choices=[(b'preparing', '\u041d\u0430\u043f\u043e\u043b\u043d\u0435\u043d\u0438\u0435/\u041f\u043e\u0434\u0433\u043e\u0442\u043e\u0432\u043a\u0430 \u043a \u043e\u0442\u043f\u0440\u0430\u0432\u043a\u0435'), (b'ready_for_test', '\u0413\u043e\u0442\u043e\u0432\u043e \u043a \u0442\u0435\u0441\u0442\u043e\u0432\u043e\u0439 \u043e\u0442\u043f\u0440\u0430\u0432\u043a\u0435'), (b'ready', '\u0413\u043e\u0442\u043e\u0432\u043e \u043a \u043e\u0442\u043f\u0440\u0430\u0432\u043a\u0435'), (b'process', '\u0412 \u043f\u0440\u043e\u0446\u0435\u0441\u0441\u0435 \u043e\u0442\u043f\u0440\u0430\u0432\u043a\u0438'), (b'done', '\u041f\u0440\u0438\u0433\u043b\u0430\u0448\u0435\u043d\u0438\u044f \u0440\u0430\u0437\u043e\u0441\u043b\u0430\u043d\u044b')], default=b'preparing', max_length=15, verbose_name='\u0441\u0442\u0430\u0442\u0443\u0441 \u0440\u0430\u0441\u0441\u044b\u043b\u043a\u0438 \u043f\u0440\u0438\u0433\u043b\u0430\u0448\u0435\u043d\u0438\u044f'),
        ),
    ]
