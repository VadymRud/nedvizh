# -*- coding: utf-8 -*-
# Generated by Django 1.9.10 on 2017-02-20 14:49
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('webinars', '0006_auto_20170220_1244'),
    ]

    operations = [
        migrations.AddField(
            model_name='webinar',
            name='address',
            field=models.CharField(blank=True, help_text='\u0418\u0441\u043f\u043e\u043b\u044c\u0437\u0443\u0435\u0442\u0441\u044f \u0434\u043b\u044f \u0440\u0430\u0441\u0441\u044b\u043b\u043a\u0438 \u043f\u0440\u0438\u0433\u043b\u0430\u0448\u0435\u043d\u0438\u044f \u043d\u0430 \u0441\u0435\u043c\u0438\u043d\u0430\u0440.', max_length=255, null=True, verbose_name='\u0410\u0434\u0440\u0435\u0441 \u043f\u0440\u043e\u0432\u0435\u0434\u0435\u043d\u0438\u044f \u0441\u0435\u043c\u0438\u043d\u0430\u0440\u0430'),
        ),
        migrations.AddField(
            model_name='webinar',
            name='address_hu',
            field=models.CharField(blank=True, help_text='\u0418\u0441\u043f\u043e\u043b\u044c\u0437\u0443\u0435\u0442\u0441\u044f \u0434\u043b\u044f \u0440\u0430\u0441\u0441\u044b\u043b\u043a\u0438 \u043f\u0440\u0438\u0433\u043b\u0430\u0448\u0435\u043d\u0438\u044f \u043d\u0430 \u0441\u0435\u043c\u0438\u043d\u0430\u0440.', max_length=255, null=True, verbose_name='\u0410\u0434\u0440\u0435\u0441 \u043f\u0440\u043e\u0432\u0435\u0434\u0435\u043d\u0438\u044f \u0441\u0435\u043c\u0438\u043d\u0430\u0440\u0430'),
        ),
        migrations.AddField(
            model_name='webinar',
            name='address_ru',
            field=models.CharField(blank=True, help_text='\u0418\u0441\u043f\u043e\u043b\u044c\u0437\u0443\u0435\u0442\u0441\u044f \u0434\u043b\u044f \u0440\u0430\u0441\u0441\u044b\u043b\u043a\u0438 \u043f\u0440\u0438\u0433\u043b\u0430\u0448\u0435\u043d\u0438\u044f \u043d\u0430 \u0441\u0435\u043c\u0438\u043d\u0430\u0440.', max_length=255, null=True, verbose_name='\u0410\u0434\u0440\u0435\u0441 \u043f\u0440\u043e\u0432\u0435\u0434\u0435\u043d\u0438\u044f \u0441\u0435\u043c\u0438\u043d\u0430\u0440\u0430'),
        ),
        migrations.AddField(
            model_name='webinar',
            name='address_uk',
            field=models.CharField(blank=True, help_text='\u0418\u0441\u043f\u043e\u043b\u044c\u0437\u0443\u0435\u0442\u0441\u044f \u0434\u043b\u044f \u0440\u0430\u0441\u0441\u044b\u043b\u043a\u0438 \u043f\u0440\u0438\u0433\u043b\u0430\u0448\u0435\u043d\u0438\u044f \u043d\u0430 \u0441\u0435\u043c\u0438\u043d\u0430\u0440.', max_length=255, null=True, verbose_name='\u0410\u0434\u0440\u0435\u0441 \u043f\u0440\u043e\u0432\u0435\u0434\u0435\u043d\u0438\u044f \u0441\u0435\u043c\u0438\u043d\u0430\u0440\u0430'),
        ),
    ]