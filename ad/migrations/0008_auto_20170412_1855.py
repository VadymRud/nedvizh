# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-04-12 18:55
from __future__ import unicode_literals

import datetime
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('ad', '0007_auto_20170405_1328'),
    ]

    operations = [
        migrations.CreateModel(
            name='DeactivationForSale',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.PositiveIntegerField(choices=[(1, '\u043e\u0431\u044a\u0435\u043a\u0442 \u043f\u0440\u043e\u0434\u0430\u043d \u043d\u0430 Mesto.ua'), (2, '\u043e\u0431\u044a\u0435\u043a\u0442 \u043f\u0440\u043e\u0434\u0430\u043d \u043d\u0430 \u0434\u0440\u0443\u0433\u043e\u043c \u0441\u0430\u0439\u0442\u0435'), (3, '\u043e\u0431\u044a\u0435\u043a\u0442 \u043f\u0440\u043e\u0434\u0430\u043b \u043a\u043e\u043b\u043b\u0435\u0433\u0430'), (4, '\u0432\u043b\u0430\u0434\u0435\u043b\u0435\u0446 \u043f\u0435\u0440\u0435\u0434\u0443\u043c\u0430\u043b'), (5, '\u0434\u0440\u0443\u0433\u0430\u044f \u043f\u0440\u0438\u0447\u0438\u043d\u0430')], verbose_name='\u043f\u0440\u0438\u0447\u0438\u043d\u0430 \u0441\u043d\u044f\u0442\u0438\u044f \u0441 \u043f\u0440\u043e\u0434\u0430\u0436\u0438')),
                ('deactivation_time', models.DateTimeField(default=datetime.datetime.now, verbose_name='\u0432\u0440\u0435\u043c\u044f \u0434\u0435\u0430\u043a\u0442\u0438\u0432\u0430\u0446\u0438\u0438')),
                ('returning_time', models.DateTimeField(blank=True, null=True, verbose_name='\u0432\u0440\u0435\u043c\u044f \u0432\u043e\u0437\u0432\u0440\u0430\u0442\u0430 \u043a \u043f\u0443\u0431\u043b\u0438\u043a\u0430\u0446\u0438\u0438')),
                ('basead', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='deactivations', to='ad.BaseAd', verbose_name='\u043e\u0431\u044a\u044f\u0432\u043b\u0435\u043d\u0438\u0435')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044c')),
            ],
            options={
                'verbose_name': '\u043f\u0440\u0438\u0447\u0438\u043d\u0430 \u0434\u0435\u0430\u043a\u0442\u0438\u0432\u0430\u0446\u0438\u0438',
                'verbose_name_plural': '\u043f\u0440\u0438\u0447\u0438\u043d\u044b \u0434\u0435\u0430\u043a\u0442\u0438\u0432\u0430\u0446\u0438\u0438',
            },
        ),
        migrations.RemoveField(
            model_name='ad',
            name='is_sold',
        ),
    ]