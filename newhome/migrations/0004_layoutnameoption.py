# -*- coding: utf-8 -*-
# Generated by Django 1.9.10 on 2017-01-30 13:50
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('newhome', '0003_auto_20170119_1629'),
    ]

    operations = [
        migrations.CreateModel(
            name='LayoutNameOption',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='\u0412\u0432\u0435\u0434\u0438\u0442\u0435 \u043d\u0430\u0437\u0432\u0430\u043d\u0438\u0435 \u043f\u043b\u0430\u043d\u0438\u0440\u043e\u0432\u043a\u0438', max_length=50, verbose_name='\u043d\u0430\u0437\u0432\u0430\u043d\u0438\u0435')),
                ('name_ru', models.CharField(help_text='\u0412\u0432\u0435\u0434\u0438\u0442\u0435 \u043d\u0430\u0437\u0432\u0430\u043d\u0438\u0435 \u043f\u043b\u0430\u043d\u0438\u0440\u043e\u0432\u043a\u0438', max_length=50, null=True, verbose_name='\u043d\u0430\u0437\u0432\u0430\u043d\u0438\u0435')),
                ('name_uk', models.CharField(help_text='\u0412\u0432\u0435\u0434\u0438\u0442\u0435 \u043d\u0430\u0437\u0432\u0430\u043d\u0438\u0435 \u043f\u043b\u0430\u043d\u0438\u0440\u043e\u0432\u043a\u0438', max_length=50, null=True, verbose_name='\u043d\u0430\u0437\u0432\u0430\u043d\u0438\u0435')),
                ('name_hu', models.CharField(help_text='\u0412\u0432\u0435\u0434\u0438\u0442\u0435 \u043d\u0430\u0437\u0432\u0430\u043d\u0438\u0435 \u043f\u043b\u0430\u043d\u0438\u0440\u043e\u0432\u043a\u0438', max_length=50, null=True, verbose_name='\u043d\u0430\u0437\u0432\u0430\u043d\u0438\u0435')),
            ],
            options={
                'verbose_name': '\u0432\u0430\u0440\u0438\u0430\u043d\u0442',
                'verbose_name_plural': '\u0432\u0430\u0440\u0438\u0430\u043d\u0442\u044b \u043d\u0430\u0437\u0432\u0430\u043d\u0438\u0439 \u043f\u043b\u0430\u043d\u0438\u0440\u043e\u0432\u043a\u0438',
            },
        ),
    ]
