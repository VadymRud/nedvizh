# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-05-31 21:50
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
import jsonfield.fields


def update_added_fields(apps, schema_editor):
    for search in apps.get_model('profile', 'SavedSearch').objects.all():
        parameters = dict(search.parameters)
        search.deal_type = parameters.pop('deal_type')
        search.property_type = parameters.pop('property_type')
        search.region_id = parameters.pop('region')
        search.query_parameters = parameters
        search.save()


class Migration(migrations.Migration):

    dependencies = [
        ('ad', '0010_ad_iframe_url'),
        ('profile', '0009_delete_old_savedsearches_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='savedsearch',
            name='deal_type',
            field=models.CharField(choices=[(b'rent', '\u0430\u0440\u0435\u043d\u0434\u0430'), (b'rent_daily', '\u043f\u043e\u0441\u0443\u0442\u043e\u0447\u043d\u0430\u044f \u0430\u0440\u0435\u043d\u0434\u0430'), (b'sale', '\u043f\u0440\u043e\u0434\u0430\u0436\u0430')], max_length=20, null=True, verbose_name='\u0442\u0438\u043f \u043e\u043f\u0435\u0440\u0430\u0446\u0438\u0438'),
        ),
        migrations.AddField(
            model_name='savedsearch',
            name='property_type',
            field=models.CharField(choices=[(b'all-real-estate', '\u0432\u0441\u044f \u043d\u0435\u0434\u0432\u0438\u0436\u0438\u043c\u043e\u0441\u0442\u044c'), (b'flat', '\u043a\u0432\u0430\u0440\u0442\u0438\u0440\u0430'), (b'room', '\u043a\u043e\u043c\u043d\u0430\u0442\u0430'), (b'house', '\u0434\u043e\u043c'), (b'plot', '\u0443\u0447\u0430\u0441\u0442\u043e\u043a'), (b'commercial', '\u043a\u043e\u043c\u043c\u0435\u0440\u0447\u0435\u0441\u043a\u0430\u044f \u043d\u0435\u0434\u0432\u0438\u0436\u0438\u043c\u043e\u0441\u0442\u044c'), (b'garages', '\u0433\u0430\u0440\u0430\u0436\u0438')], max_length=20, null=True, verbose_name='\u0442\u0438\u043f \u043d\u0435\u0434\u0432\u0438\u0436\u0438\u043c\u043e\u0441\u0442\u0438'),
        ),
        migrations.AddField(
            model_name='savedsearch',
            name='query_parameters',
            field=jsonfield.fields.JSONField(default=dict, verbose_name='GET-\u043f\u0430\u0440\u0430\u043c\u0435\u0442\u0440\u044b'),
        ),
        migrations.AddField(
            model_name='savedsearch',
            name='region',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='ad.Region', verbose_name='\u0433\u043e\u0440\u043e\u0434'),
        ),
        migrations.RunPython(update_added_fields, migrations.RunPython.noop),
    ]
