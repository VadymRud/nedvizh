# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-07-19 18:21
from __future__ import unicode_literals

from django.db import migrations, models

def create_managers(apps, schema_editor):
    Message = apps.get_model('profile', 'Message')

    # рассылки
    Message.objects.filter(message_list__isnull=False).update(text_type='html')

    # сообщения со ссылками для подтверждения риелторов
    Q_realtor_confirm = models.Q(text__contains='mesto.ua/account/agency/realtors/add/confirm/') | \
                        models.Q(text__contains='mesto.ua/uk/account/agency/realtors/add/confirm/') | \
                        models.Q(text__contains='mesto.ua/rc/') | models.Q(text__contains='mesto.ua/uk/rc/')
    Message.objects.filter(root_message=models.F('id')).filter(Q_realtor_confirm).update(text_type='html')

class Migration(migrations.Migration):

    dependencies = [
        ('profile', '0011_savedsearch_split_parameters_2nd_step'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='text_type',
            field=models.CharField(choices=[(b'text', 'plain text'), (b'html', 'HTML')], default=b'text', max_length=5, verbose_name='\u0444\u043e\u0440\u043c\u0430\u0442 \u0442\u0435\u043a\u0441\u0442\u0430 \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u044f'),
        ),
        migrations.RunPython(create_managers, migrations.RunPython.noop),
    ]
