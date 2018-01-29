# -*- coding: utf-8 -*-
# Generated by Django 1.9.10 on 2016-12-29 04:26
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ppc', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='activityperiod',
            options={'verbose_name': '\u043f\u0435\u0440\u0438\u043e\u0434', 'verbose_name_plural': '\u043f\u0435\u0440\u0438\u043e\u0434\u044b'},
        ),
        migrations.AlterModelOptions(
            name='bonus',
            options={'verbose_name': '\u0431\u043e\u043d\u0443\u0441\u044b', 'verbose_name_plural': '\u0431\u043e\u043d\u0443\u0441\u044b'},
        ),
        migrations.AlterModelOptions(
            name='leadgeneration',
            options={'verbose_name': '\u043d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0430', 'verbose_name_plural': '\u043d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438'},
        ),
        migrations.AlterModelOptions(
            name='proxynumber',
            options={'verbose_name': '\u0442\u0435\u043b\u0435\u0444\u043e\u043d\u043d\u044b\u0439 \u043d\u043e\u043c\u0435\u0440', 'verbose_name_plural': '\u0442\u0435\u043b\u0435\u0444\u043e\u043d\u043d\u044b\u0435 \u043d\u043e\u043c\u0435\u0440\u0430'},
        ),
        migrations.AddField(
            model_name='leadgeneration',
            name='dedicated_numbers',
            field=models.BooleanField(default=False, verbose_name='\u0432\u044b\u0434\u0435\u043b\u0435\u043d\u043d\u044b\u0435 \u043d\u043e\u043c\u0435\u0440\u0430'),
        ),
        migrations.AddField(
            model_name='leadgeneration',
            name='use_old_numbers',
            field=models.BooleanField(default=True, verbose_name='\u0438\u0441\u043f\u043e\u043b\u044c\u0437\u0443\u044e\u0442\u0441\u044f \u043d\u043e\u043c\u0435\u0440\u0430 \u043e\u0444\u0438\u0441\u043d\u043e\u0439 \u0442\u0435\u043b\u0435\u0444\u043e\u043d\u0438\u0438'),
        ),
        migrations.AddField(
            model_name='proxynumber',
            name='is_shared',
            field=models.BooleanField(default=False, verbose_name='\u043e\u0431\u0449\u0438\u0439 \u043d\u043e\u043c\u0435\u0440'),
        ),
        migrations.AddField(
            model_name='proxynumber',
            name='provider',
            field=models.CharField(choices=[(b'local', '\u043e\u0444\u0438\u0441\u043d\u0430\u044f \u0442\u0435\u043b\u0435\u0444\u043e\u043d\u0438\u044f'), (b'ringostat', 'RingoStat')], default='local', max_length=10, verbose_name='\u043f\u0440\u043e\u0432\u0430\u0439\u0434\u0435\u0440 \u043d\u043e\u043c\u0435\u0440\u0430'),
            preserve_default=False,
        ),
    ]