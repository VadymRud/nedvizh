# -*- coding: utf-8 -*-
# Generated by Django 1.9.10 on 2017-01-13 17:21
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ppc', '0004_new_numbers'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='call',
            options={'verbose_name': '\u0437\u0432\u043e\u043d\u043e\u043a', 'verbose_name_plural': '\u0437\u0432\u043e\u043d\u043a\u0438'},
        ),
        migrations.AlterModelOptions(
            name='proxynumber',
            options={'verbose_name': '\u043d\u043e\u043c\u0435\u0440 \u043f\u0435\u0440\u0435\u0430\u0434\u0440\u0435\u0441\u0430\u0446\u0438\u0438', 'verbose_name_plural': '\u043d\u043e\u043c\u0435\u0440\u0430 \u043f\u0435\u0440\u0435\u0430\u0434\u0440\u0435\u0441\u0430\u0446\u0438\u0438'},
        ),
        migrations.AddField(
            model_name='call',
            name='proxynumber',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='calls', to='ppc.ProxyNumber', verbose_name='\u043d\u043e\u043c\u0435\u0440 \u043f\u0435\u0440\u0435\u0430\u0434\u0440\u0435\u0441\u0430\u0446\u0438\u0438'),
        ),
    ]
