# -*- coding: utf-8 -*-
# Generated by Django 1.9.10 on 2017-01-17 11:55
from __future__ import unicode_literals

from django.db import migrations, models
from django.db.models import F


def forwards(apps, schema_editor):
    Newhome = apps.get_model('newhome', 'Newhome')
    Newhome.objects.exclude(developer='').update(
        seller=F('developer'), seller_ru=F('developer_ru'), seller_hu=F('developer_hu'), seller_uk=F('developer_uk'))

    Newhome.objects.all().update(developer='', developer_ru='', developer_uk='', developer_hu='')


class Migration(migrations.Migration):

    dependencies = [
        ('newhome', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='newhome',
            name='seller',
            field=models.CharField(default='', max_length=50, verbose_name='\u0440\u0435\u0430\u043b\u0438\u0437\u0443\u0435\u0442'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='newhome',
            name='seller_hu',
            field=models.CharField(max_length=50, null=True, verbose_name='\u0440\u0435\u0430\u043b\u0438\u0437\u0443\u0435\u0442'),
        ),
        migrations.AddField(
            model_name='newhome',
            name='seller_ru',
            field=models.CharField(max_length=50, null=True, verbose_name='\u0440\u0435\u0430\u043b\u0438\u0437\u0443\u0435\u0442'),
        ),
        migrations.AddField(
            model_name='newhome',
            name='seller_uk',
            field=models.CharField(max_length=50, null=True, verbose_name='\u0440\u0435\u0430\u043b\u0438\u0437\u0443\u0435\u0442'),
        ),
        migrations.AlterField(
            model_name='newhome',
            name='developer',
            field=models.CharField(blank=True, max_length=50, verbose_name='\u0437\u0430\u0441\u0442\u0440\u043e\u0439\u0449\u0438\u043a'),
        ),
        migrations.AlterField(
            model_name='newhome',
            name='developer_hu',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='\u0437\u0430\u0441\u0442\u0440\u043e\u0439\u0449\u0438\u043a'),
        ),
        migrations.AlterField(
            model_name='newhome',
            name='developer_ru',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='\u0437\u0430\u0441\u0442\u0440\u043e\u0439\u0449\u0438\u043a'),
        ),
        migrations.AlterField(
            model_name='newhome',
            name='developer_uk',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='\u0437\u0430\u0441\u0442\u0440\u043e\u0439\u0449\u0438\u043a'),
        ),
        migrations.RunPython(forwards, migrations.RunPython.noop)
    ]
