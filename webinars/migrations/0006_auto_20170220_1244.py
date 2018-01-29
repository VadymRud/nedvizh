# -*- coding: utf-8 -*-
# Generated by Django 1.9.10 on 2017-02-20 12:44
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('webinars', '0005_webinar_emails_sent'),
    ]

    operations = [
        migrations.AddField(
            model_name='webinar',
            name='external_url',
            field=models.URLField(blank=True, max_length=255, null=True, verbose_name='\u0421\u0441\u044b\u043b\u043a\u0430 \u043d\u0430 \u043a\u043e\u043c\u043d\u0430\u0442\u0443 \u043f\u0440\u043e\u0432\u0435\u0434\u0435\u043d\u0438\u044f \u0441\u0435\u043c\u0438\u043d\u0430\u0440\u0430'),
        ),
        migrations.AlterField(
            model_name='webinarreminder',
            name='webinar',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reminders', to='webinars.Webinar', verbose_name='\u0412\u0435\u0431\u0438\u043d\u0430\u0440'),
        ),
    ]
