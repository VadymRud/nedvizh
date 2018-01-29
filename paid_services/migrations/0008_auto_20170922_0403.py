# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-09-22 04:03
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('paid_services', '0007_auto_20170616_1215'),
    ]

    operations = [
        migrations.AlterField(
            model_name='transaction',
            name='type',
            field=models.PositiveIntegerField(choices=[(1, '\u043f\u043e\u043f\u043e\u043b\u043d: \u0431\u043e\u043d\u0443\u0441'), (2, '\u043f\u043e\u043f\u043e\u043b\u043d: \u043f\u043b\u0430\u0442\u0435\u0436\u043d\u0430\u044f \u0441\u0438\u0441\u0442\u0435\u043c\u0430'), (31, '\u0432\u043e\u0437\u0432\u0440\u0430\u0442 \u043e\u0441\u0442\u0430\u0442\u043a\u0430 \u0437\u0430 \u043f\u0430\u043a\u0435\u0442 \u043e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u0439'), (32, '\u0432\u043e\u0437\u0432\u0440\u0430\u0442 \u043f\u0440\u0438 \u043e\u0442\u043c\u0435\u043d\u0435 \u0442\u0430\u0440\u0438\u0444\u0430'), (33, '\u0432\u043e\u0437\u0432\u0440\u0430\u0442 \u043e\u0441\u0442\u0430\u0442\u043a\u0430 \u043f\u0440\u0438 \u043e\u0441\u0442\u0430\u043d\u043e\u0432\u043a\u0435 \u0442\u0430\u0440\u0438\u0444\u0430'), (4, '\u043f\u043e\u043f\u043e\u043b\u043d: \u043d\u043e\u0432\u043e\u0433\u043e\u0434\u043d\u044f\u044f \u0430\u043a\u0446\u0438\u044f'), (5, '\u043f\u043e\u043f\u043e\u043b\u043d: \u0447\u0435\u0440\u0435\u0437 \u043f\u0440\u043e\u043c\u043e-\u043a\u043e\u0434'), (6, '\u043f\u043e\u043f\u043e\u043b\u043d: \u0431\u043e\u043d\u0443\u0441 \u043f\u0440\u0438 \u0440\u0435\u0433\u0438\u0441\u0442\u0440\u0430\u0446\u0438\u0438'), (7, '\u043f\u043e\u043f\u043e\u043b\u043d: \u0441\u0447\u0435\u0442-\u0444\u0430\u043a\u0442\u0443\u0440\u0430'), (9, '\u043f\u043e\u043f\u043e\u043b\u043d: \u0431\u043e\u043d\u0443\u0441 \u0441 \u0422\u0412 \u0440\u0435\u043a\u043b\u0430\u043c\u044b'), (93, '\u043f\u043e\u043f\u043e\u043b\u043d: \u0431\u043e\u043d\u0443\u0441 \u043f\u043e \u0441\u0438\u0441\u0442\u0435\u043c\u0435 \u043b\u043e\u044f\u043b\u044c\u043d\u043e\u0441\u0442\u0438'), (8, '\u043f\u0435\u0440\u0435\u0432\u043e\u0434: \u043a \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044e'), (21, '\u043f\u0435\u0440\u0435\u0432\u043e\u0434: \u043e\u0442 \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044f'), (11, '\u0442\u0430\u0440\u0438\u0444: \u043f\u043e\u043a\u0443\u043f\u043a\u0430'), (12, '\u0442\u0430\u0440\u0438\u0444: \u0443\u043b\u0443\u0447\u0448\u0435\u043d\u0438\u0435'), (51, '\u043e\u043f\u043b\u0430\u0442\u0430 \u043f\u0440\u0435\u043c\u0438\u0443\u043c \u043e\u0431\u044a\u044f\u0432\u043b\u0435\u043d\u0438\u044f'), (52, '\u043e\u043f\u043b\u0430\u0442\u0430 \u044d\u043a\u0441\u043a\u043b\u044e\u0437\u0438\u0432\u043d\u043e\u0433\u043e \u043e\u0431\u044a\u044f\u0432\u043b\u0435\u043d\u0438\u044f'), (53, '\u0440\u0430\u0437\u043c\u0435\u0449: VIP'), (54, '\u0440\u0430\u0437\u043c\u0435\u0449: \u0437\u0430\u0440\u0443\u0431\u0435\u0436 mesto.ua'), (55, '\u0440\u0430\u0437\u043c\u0435\u0449: \u0437\u0430\u0440\u0443\u0431\u0435\u0436 \u043f\u0430\u0440\u0442\u043d\u0435\u0440\u044b'), (3, '\u0440\u0430\u0437\u043c\u0435\u0449: \u0432\u043e\u0437\u0432\u0440\u0430\u0442'), (61, '\u043e\u043f\u043b\u0430\u0442\u0430 \u0441\u0447\u0435\u0442\u0430 \u043f\u043e \u043f\u043e\u0441\u0443\u0442\u043e\u0447\u043d\u043e\u0439 \u0430\u0440\u0435\u043d\u0434\u0435'), (62, '\u043e\u043f\u043b\u0430\u0442\u0430 \u0443\u0447\u0430\u0441\u0442\u0438\u044f \u0432 \u0442\u0440\u0435\u043d\u0438\u043d\u0433\u0435'), (71, '\u043e\u043f\u043b\u0430\u0442\u0430 \u043e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u044f \u043e\u0431\u044a\u044f\u0432\u043b\u0435\u043d\u0438\u0439'), (80, '\u043e\u043f\u043b\u0430\u0442\u0430 \u0437\u0430 \u0432\u044b\u0434\u0435\u043b\u0435\u043d\u043d\u044b\u0439 \u043d\u043e\u043c\u0435\u0440'), (81, '\u043e\u043f\u043b\u0430\u0442\u0430 \u043f\u0440\u043e\u0434\u043b\u0435\u043d\u0438\u044f CRM'), (82, '\u043f\u043f\u043a: \u043b\u0438\u0434 (\u0443\u0441\u0442\u0430\u0440\u0435\u0432\u0448)'), (83, '\u043f\u043f\u043a: \u0437\u0430\u043a\u0430\u0437'), (84, '\u043f\u043f\u043a: \u0437\u0432\u043e\u043d\u043e\u043a'), (85, '\u043f\u043f\u043a: \u0437\u0432\u043e\u043d\u043e\u043a \u043f\u0440\u043e\u043f\u0443\u0449'), (34, '\u043f\u043f\u043a: \u0432\u043e\u0437\u0432\u0440\u0430\u0442 \u0437\u0430 \u0437\u0432\u043e\u043d\u043e\u043a'), (91, '\u043e\u043f\u043b\u0430\u0442\u0430 \u043f\u0430\u043a\u0435\u0442\u043d\u043e\u0433\u043e \u043e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u044f'), (92, '\u043e\u043f\u043b\u0430\u0442\u0430 \u0430\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u043e\u0433\u043e \u043e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u044f')], db_index=True, default=0, verbose_name='\u0442\u0438\u043f'),
        ),
    ]
