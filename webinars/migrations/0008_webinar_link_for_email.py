# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-12-01 16:30
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('webinars', '0007_auto_20170220_1449'),
    ]

    operations = [
        migrations.AddField(
            model_name='webinar',
            name='link_for_email',
            field=models.URLField(blank=True, max_length=255, null=True, verbose_name='\u0421\u0441\u044b\u043b\u043a\u0430 \u043d\u0430 \u0441\u0442\u0440\u0430\u043d\u0438\u0446\u0443 \u0441\u0435\u043c\u0438\u043d\u0430\u0440\u0430 \u0434\u043b\u044f \u0440\u0430\u0441\u0441\u044b\u043b\u043a\u0438'),
        ),
    ]
