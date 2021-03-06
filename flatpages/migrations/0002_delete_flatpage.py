# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-08-16 18:42
from __future__ import unicode_literals

from django.db import migrations


# почему-то не удаляется автоматически после команды migrate, приходится вручную
def delete_flatpage_contenttype(apps, schema_editor):
    from django.contrib.contenttypes.models import ContentType
    ContentType.objects.get(app_label='flatpages', model='flatpage').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('flatpages', '0001_initial'),
        ('staticpages', '0004_delete_extendedflatpage'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='flatpage',
            name='sites',
        ),
        migrations.DeleteModel(
            name='FlatPage',
        ),
        migrations.RunPython(delete_flatpage_contenttype, migrations.RunPython.noop),
    ]
