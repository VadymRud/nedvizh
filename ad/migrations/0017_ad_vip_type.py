# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-10-06 11:51
from __future__ import unicode_literals

from django.db import migrations, models


def update_vip_type(apps, schema_editor):
    from ad.models import Ad
    from paid_services.models import VipPlacement  # у VipPlacement кастомный objects, который недоступен при apps.get_model()
    Ad.objects.filter(pk__in=VipPlacement.objects.filter(is_active=True).values('basead')).update(vip_type=1)


class Migration(migrations.Migration):

    dependencies = [
        ('ad', '0016_auto_20171005_1910'),
        ('paid_services', '0010_vipplacement_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='ad',
            name='vip_type',
            field=models.PositiveIntegerField(choices=[(0, 0), (1, 1)], default=0, verbose_name='\u0442\u0438\u043f VIP-\u0440\u0430\u0437\u043c\u0435\u0449\u0435\u043d\u0438\u044f'),
        ),
        migrations.RunPython(update_vip_type, migrations.RunPython.noop),
    ]
