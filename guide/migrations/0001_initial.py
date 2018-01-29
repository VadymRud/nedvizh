# -*- coding: utf-8 -*-
# Generated by Django 1.9.10 on 2016-12-29 00:23
from __future__ import unicode_literals

import dirtyfields.dirtyfields
from django.db import migrations, models
import django.db.models.deletion
import guide.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('ad', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Cinema',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(choices=[(b'cinema', '\u043a\u0438\u043d\u043e\u0442\u0435\u0430\u0442\u0440'), (b'theatre', '\u0442\u0435\u0430\u0442\u0440'), (b'opera', '\u043e\u043f\u0435\u0440\u0430')], max_length=20, verbose_name='\u0442\u0438\u043f')),
                ('name', models.CharField(max_length=200, verbose_name='\u043d\u0430\u0437\u0432\u0430\u043d\u0438\u0435')),
                ('relative_address', models.CharField(help_text='\u0443\u043b\u0438\u0446\u0430, \u0434\u043e\u043c', max_length=100, verbose_name='\u0430\u0434\u0440\u0435\u0441')),
                ('phone1', models.CharField(blank=True, max_length=200, null=True, verbose_name='\u0442\u0435\u043b\u0435\u0444\u043e\u043d')),
                ('phone2', models.CharField(blank=True, max_length=200, null=True, verbose_name='\u0434\u043e\u043f. \u0442\u0435\u043b\u0435\u0444\u043e\u043d')),
                ('subdomain', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='guide_cinema', to='ad.Region', verbose_name='\u0433\u043e\u0440\u043e\u0434/\u043f\u043e\u0434\u0434\u043e\u043c\u0435\u043d')),
            ],
            options={
                'verbose_name': '\u043a\u0438\u043d\u043e\u0442\u0435\u0430\u0442\u0440',
                'verbose_name_plural': '\u043a\u0438\u043d\u043e\u0442\u0435\u0430\u0442\u0440\u044b',
            },
        ),
        migrations.CreateModel(
            name='Cookery',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, verbose_name='\u043d\u0430\u0437\u0432\u0430\u043d\u0438\u0435')),
            ],
            options={
                'verbose_name': '\u043a\u0443\u0445\u043d\u044f',
                'verbose_name_plural': '\u043a\u0443\u0445\u043d\u0438',
            },
        ),
        migrations.CreateModel(
            name='Photo',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('added', models.DateTimeField(auto_now_add=True, verbose_name='\u0434\u043e\u0431\u0430\u0432\u043b\u0435\u043d\u0430')),
                ('image', models.ImageField(upload_to=b'upload/guide/photo/', verbose_name='\u0438\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u0435')),
                ('description', models.TextField(blank=True, null=True, verbose_name='\u043e\u043f\u0438\u0441\u0430\u043d\u0438\u0435')),
                ('likes', models.PositiveIntegerField(default=0, verbose_name='\u043b\u0430\u0439\u043a\u0438')),
                ('subdomain', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='guide_photos', to='ad.Region', verbose_name='\u043f\u043e\u0434\u0434\u043e\u043c\u0435\u043d')),
            ],
            options={
                'verbose_name': '\u0444\u043e\u0442\u043e\u0433\u0440\u0430\u0444\u0438\u044f',
                'verbose_name_plural': '\u0444\u043e\u0442\u043e\u0433\u0440\u0430\u0444\u0438\u0438',
            },
        ),
        migrations.CreateModel(
            name='Restaurant',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='\u043d\u0430\u0437\u0432\u0430\u043d\u0438\u0435')),
                ('address', models.CharField(help_text=b'\xd0\x9d\xd0\xb0\xd0\xbf\xd1\x80\xd0\xb8\xd0\xbc\xd0\xb5\xd1\x80: \xd0\x9a\xd0\xb8\xd0\xb5\xd0\xb2, \xd1\x83\xd0\xbb. \xd0\x9a\xd1\x80\xd0\xb5\xd1\x89\xd0\xb0\xd1\x82\xd0\xb8\xd0\xba, 24', max_length=255, verbose_name=b'\xd0\xbf\xd0\xbe\xd0\xbb\xd0\xbd\xd1\x8b\xd0\xb9 \xd0\xb0\xd0\xb4\xd1\x80\xd0\xb5\xd1\x81')),
                ('description', models.TextField(blank=True, null=True, verbose_name='\u043e\u043f\u0438\u0441\u0430\u043d\u0438\u0435')),
                ('phone', models.CharField(blank=True, max_length=200, null=True, verbose_name='\u0442\u0435\u043b\u0435\u0444\u043e\u043d')),
                ('parking', models.NullBooleanField(verbose_name='\u043f\u0430\u0440\u043a\u043e\u0432\u043a\u0430')),
                ('payment', models.CharField(blank=True, max_length=200, null=True, verbose_name='\u0442\u0438\u043f \u043e\u043f\u043b\u0430\u0442\u044b')),
                ('notes', models.TextField(blank=True, null=True, verbose_name='\u043f\u0440\u0438\u043c\u0435\u0447\u0430\u043d\u0438\u044f')),
                ('coords_x', models.CharField(blank=True, max_length=12, null=True, verbose_name=b'\xd0\xba\xd0\xbe\xd0\xbe\xd1\x80\xd0\xb4\xd0\xb8\xd0\xbd\xd0\xb0\xd1\x82\xd1\x8b \xd0\xbf\xd0\xbe X')),
                ('coords_y', models.CharField(blank=True, max_length=12, null=True, verbose_name=b'\xd0\xba\xd0\xbe\xd0\xbe\xd1\x80\xd0\xb4\xd0\xb8\xd0\xbd\xd0\xb0\xd1\x82\xd1\x8b \xd0\xbf\xd0\xbe Y')),
                ('likes', models.PositiveIntegerField(default=0, verbose_name='\u043b\u0430\u0439\u043a\u0438')),
                ('image', models.ImageField(blank=True, null=True, upload_to=guide.models.restaurant_upload_path, verbose_name='\u0438\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u0435')),
                ('working_hours', models.CharField(blank=True, max_length=200, null=True, verbose_name='\u0432\u0440\u0435\u043c\u044f \u0440\u0430\u0431\u043e\u0442\u044b')),
                ('rooms', models.PositiveIntegerField(blank=True, null=True, verbose_name='\u043a\u043e\u043b\u0438\u0447\u0435\u0441\u0442\u0432\u043e \u0437\u0430\u043b\u043e\u0432')),
                ('music', models.CharField(blank=True, max_length=200, null=True, verbose_name='\u043c\u0443\u0437\u044b\u043a\u0430')),
                ('entrance_fee', models.CharField(blank=True, max_length=200, null=True, verbose_name='\u043f\u043b\u0430\u0442\u0430 \u0437\u0430 \u0432\u0445\u043e\u0434')),
                ('site', models.CharField(blank=True, max_length=50, null=True, verbose_name='\u0441\u0430\u0439\u0442')),
                ('cookeries', models.ManyToManyField(to='guide.Cookery', verbose_name='\u043a\u0443\u0445\u043d\u0438')),
                ('region', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='region_restaurants', to='ad.Region', verbose_name=b'\xd0\xbf\xd1\x80\xd0\xb8\xd1\x81\xd0\xb2\xd0\xbe\xd0\xb5\xd0\xbd\xd0\xbd\xd1\x8b\xd0\xb9 \xd1\x80\xd0\xb5\xd0\xb3\xd0\xb8\xd0\xbe\xd0\xbd')),
            ],
            options={
                'verbose_name': '\u0440\u0435\u0441\u0442\u043e\u0440\u0430\u043d',
                'verbose_name_plural': '\u0440\u0435\u0441\u0442\u043e\u0440\u0430\u043d\u044b',
            },
            bases=(models.Model, dirtyfields.dirtyfields.DirtyFieldsMixin),
        ),
        migrations.CreateModel(
            name='RestaurantType',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, verbose_name='\u043d\u0430\u0437\u0432\u0430\u043d\u0438\u0435')),
            ],
            options={
                'verbose_name': '\u0442\u0438\u043f \u0440\u0435\u0441\u0442\u043e\u0440\u0430\u043d\u0430',
                'verbose_name_plural': '\u0442\u0438\u043f\u044b \u0440\u0435\u0441\u0442\u043e\u0440\u0430\u043d\u043e\u0432',
            },
        ),
        migrations.CreateModel(
            name='Shop',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='\u043d\u0430\u0437\u0432\u0430\u043d\u0438\u0435')),
                ('address', models.CharField(help_text=b'\xd0\x9d\xd0\xb0\xd0\xbf\xd1\x80\xd0\xb8\xd0\xbc\xd0\xb5\xd1\x80: \xd0\x9a\xd0\xb8\xd0\xb5\xd0\xb2, \xd1\x83\xd0\xbb. \xd0\x9a\xd1\x80\xd0\xb5\xd1\x89\xd0\xb0\xd1\x82\xd0\xb8\xd0\xba, 24', max_length=255, verbose_name=b'\xd0\xbf\xd0\xbe\xd0\xbb\xd0\xbd\xd1\x8b\xd0\xb9 \xd0\xb0\xd0\xb4\xd1\x80\xd0\xb5\xd1\x81')),
                ('description', models.TextField(blank=True, null=True, verbose_name='\u043e\u043f\u0438\u0441\u0430\u043d\u0438\u0435')),
                ('phone', models.CharField(blank=True, max_length=200, null=True, verbose_name='\u0442\u0435\u043b\u0435\u0444\u043e\u043d')),
                ('parking', models.NullBooleanField(verbose_name='\u043f\u0430\u0440\u043a\u043e\u0432\u043a\u0430')),
                ('payment', models.CharField(blank=True, max_length=200, null=True, verbose_name='\u0442\u0438\u043f \u043e\u043f\u043b\u0430\u0442\u044b')),
                ('notes', models.TextField(blank=True, null=True, verbose_name='\u043f\u0440\u0438\u043c\u0435\u0447\u0430\u043d\u0438\u044f')),
                ('coords_x', models.CharField(blank=True, max_length=12, null=True, verbose_name=b'\xd0\xba\xd0\xbe\xd0\xbe\xd1\x80\xd0\xb4\xd0\xb8\xd0\xbd\xd0\xb0\xd1\x82\xd1\x8b \xd0\xbf\xd0\xbe X')),
                ('coords_y', models.CharField(blank=True, max_length=12, null=True, verbose_name=b'\xd0\xba\xd0\xbe\xd0\xbe\xd1\x80\xd0\xb4\xd0\xb8\xd0\xbd\xd0\xb0\xd1\x82\xd1\x8b \xd0\xbf\xd0\xbe Y')),
                ('likes', models.PositiveIntegerField(default=0, verbose_name='\u043b\u0430\u0439\u043a\u0438')),
                ('type', models.CharField(choices=[(b'supermarket', '\u0441\u0443\u043f\u0435\u0440\u043c\u0430\u0440\u043a\u0435\u0442'), (b'building_materials', '\u0441\u0442\u0440\u043e\u0439\u043c\u0430\u0442\u0435\u0440\u0438\u0430\u043b\u044b'), (b'auto_parts', '\u0430\u0432\u0442\u043e-\u043c\u0430\u0433\u0430\u0437\u0438\u043d'), (b'household_appliances', '\u0431\u044b\u0442\u043e\u0432\u0430\u044f \u0442\u0435\u0445\u043d\u0438\u043a\u0430'), (b'shopping_centre', '\u0442\u043e\u0440\u0433\u043e\u0432\u044b\u0439 \u0446\u0435\u043d\u0442\u0440'), (b'for_children', '\u0442\u043e\u0432\u0430\u0440\u044b \u0434\u043b\u044f \u0434\u0435\u0442\u0435\u0439'), (b'flower_shop', '\u0446\u0432\u0435\u0442\u043e\u0447\u043d\u044b\u0439 \u043c\u0430\u0433\u0430\u0437\u0438\u043d')], max_length=50, verbose_name='\u0442\u0438\u043f')),
                ('image', models.ImageField(blank=True, null=True, upload_to=guide.models.shop_upload_path, verbose_name='\u0438\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u0435')),
                ('region', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='region_shops', to='ad.Region', verbose_name=b'\xd0\xbf\xd1\x80\xd0\xb8\xd1\x81\xd0\xb2\xd0\xbe\xd0\xb5\xd0\xbd\xd0\xbd\xd1\x8b\xd0\xb9 \xd1\x80\xd0\xb5\xd0\xb3\xd0\xb8\xd0\xbe\xd0\xbd')),
            ],
            options={
                'verbose_name': '\u043c\u0430\u0433\u0430\u0437\u0438\u043d',
                'verbose_name_plural': '\u043c\u0430\u0433\u0430\u0437\u0438\u043d\u044b',
            },
            bases=(models.Model, dirtyfields.dirtyfields.DirtyFieldsMixin),
        ),
        migrations.CreateModel(
            name='Taxi',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='\u043d\u0430\u0437\u0432\u0430\u043d\u0438\u0435')),
                ('image', models.ImageField(blank=True, null=True, upload_to=guide.models.make_taxi_upload_path, verbose_name='\u0438\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u0435')),
                ('description', models.TextField(blank=True, null=True, verbose_name='\u043e\u043f\u0438\u0441\u0430\u043d\u0438\u0435')),
                ('phone', models.CharField(blank=True, max_length=200, verbose_name='\u0442\u0435\u043b\u0435\u0444\u043e\u043d')),
                ('short_phone', models.CharField(blank=True, max_length=10, null=True, verbose_name='\u043a\u043e\u0440\u043e\u0442\u043a\u0438\u0439 \u043d\u043e\u043c\u0435\u0440')),
                ('min_charge', models.PositiveIntegerField(blank=True, null=True, verbose_name='\u043c\u0438\u043d\u0438\u043c\u0430\u043b\u044c\u043d\u044b\u0439 \u0442\u0430\u0440\u0438\u0444, \u0433\u0440\u043d.')),
                ('services', models.TextField(blank=True, null=True, verbose_name='\u0443\u0441\u043b\u0443\u0433\u0438')),
                ('site', models.CharField(blank=True, max_length=50, null=True, verbose_name='\u0441\u0430\u0439\u0442')),
                ('likes', models.PositiveIntegerField(default=0, verbose_name='\u043b\u0430\u0439\u043a\u0438')),
                ('subdomain', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='guide_taxi', to='ad.Region', verbose_name='\u0433\u043e\u0440\u043e\u0434/\u043f\u043e\u0434\u0434\u043e\u043c\u0435\u043d')),
            ],
            options={
                'verbose_name': '\u0442\u0430\u043a\u0441\u0438',
                'verbose_name_plural': '\u0442\u0430\u043a\u0441\u0438',
            },
        ),
        migrations.CreateModel(
            name='Video',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('youtube_id', models.CharField(max_length=50, verbose_name='Youtube ID')),
                ('name', models.CharField(max_length=200, verbose_name='\u043d\u0430\u0437\u0432\u0430\u043d\u0438\u0435')),
                ('views_count', models.PositiveIntegerField(default=0, verbose_name='\u043f\u0440\u043e\u0441\u043c\u043e\u0442\u0440\u044b')),
                ('image', models.ImageField(upload_to=b'upload/guide/video/', verbose_name='\u0438\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u0435')),
            ],
            options={
                'ordering': ('name',),
                'verbose_name': '\u0432\u0438\u0434\u0435\u043e',
                'verbose_name_plural': '\u0432\u0438\u0434\u0435\u043e',
            },
        ),
        migrations.CreateModel(
            name='WorkingHours',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('weekday', models.IntegerField(choices=[(1, '\u043f\u043e\u043d\u0435\u0434\u0435\u043b\u044c\u043d\u0438\u043a'), (2, '\u0432\u0442\u043e\u0440\u043d\u0438\u043a'), (3, '\u0441\u0440\u0435\u0434\u0430'), (4, '\u0447\u0435\u0442\u0432\u0435\u0440\u0433'), (5, '\u043f\u044f\u0442\u043d\u0438\u0446\u0430'), (6, '\u0441\u0443\u0431\u0431\u043e\u0442\u0430'), (7, '\u0432\u043e\u0441\u043a\u0440\u0435\u0441\u0435\u043d\u044c\u0435')], verbose_name='\u0434\u0435\u043d\u044c \u043d\u0435\u0434\u0435\u043b\u0438')),
                ('open', models.TimeField(verbose_name='\u043e\u0442\u043a\u0440\u044b\u0442\u0438\u0435')),
                ('close', models.TimeField(help_text='\u0432\u043c\u0435\u0441\u0442\u043e 24:00 \u0438\u0441\u043f\u043e\u043b\u044c\u0437\u0443\u0439\u0442\u0435 23:59:59', verbose_name='\u0437\u0430\u043a\u0440\u044b\u0442\u0438\u0435')),
                ('shop', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='guide.Shop', verbose_name='\u043c\u0430\u0433\u0430\u0437\u0438\u043d')),
            ],
            options={
                'verbose_name': '\u0432\u0440\u0435\u043c\u044f \u0440\u0430\u0431\u043e\u0442\u044b',
                'verbose_name_plural': '\u0432\u0440\u0435\u043c\u044f \u0440\u0430\u0431\u043e\u0442\u044b',
            },
        ),
        migrations.AddField(
            model_name='restaurant',
            name='types',
            field=models.ManyToManyField(to='guide.RestaurantType', verbose_name='\u0442\u0438\u043f\u044b'),
        ),
    ]