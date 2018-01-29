# coding=utf-8
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.conf import settings
from django.db import connection
from pytils.translit import slugify

from collections import defaultdict
import time
import random

from ad.models import *
from agency.models import *
from custom_user.models import *
from profile.models import *


class Command(BaseCommand):
    help = 'Add demo data for agency admin'

    def add_arguments(self, parser):
        parser.add_argument('--user', '-u', dest='user', type=int, default=1, help='User ID')

    def handle(self, *args, **options):
        demo_user = User.objects.get(pk=options['user'])

        # создание агентства
        if not demo_user.get_own_agency():
            agency = Agency.objects.create(name=u'Рога и копыта', show_in_agencies=False, description=u'На рынке недвижимости с 1991 года',
                                  working_hours=u'09:00-16:00', site='http://horns-n-hooves-real-estate.com/')
            realtor = Realtor.objects.create(user=demo_user, agency=agency, is_admin=True, is_active=True)
            print 'Add agency %d through realtor %d' % (agency.id, realtor.id)

        # ~30 объявлений.
        for i in xrange(30 - demo_user.ads.count()):
            ad = self.generate_ad(demo_user)
            print 'generate ad #%s' % ad.id

        # ~10 риелторов с полностью заполненной инфой (у каждого рандомное кол-во объявлений)
        for index in xrange(10):
            user = self.generate_user(index)
            self.generate_stats(user, force=False)
            Realtor.objects.get_or_create(user=user, agency=demo_user.get_own_agency(), defaults={'is_active':True})

        # ~30 лидов (с разной степенью заполненности инфы и истории)
        # 3 встречи в календаре на будущее, 1 просроченная.
        # 5 диалогов с юзерами (в тч 1 или 2 непрочитанных сообщения)
        self.generate_leads_and_tasks(demo_user, force=True)


    def generate_ad(self, user):
        ad_fields = Ad.objects.filter(vip=True, is_published=True).order_by('?').first().__dict__
        ad_fields.update({'user_id': user.id, 'vip': False, 'xml_id': 'demo'})
        for key, value in ad_fields.items():
            if key in ['id', 'basead_ptr_id'] or key.startswith('_'):
                del ad_fields[key]

        return Ad.objects.create(**ad_fields)

    def generate_user(self, index):
        username = 'user4demo%s' % index
        user, created = User.objects.get_or_create(email='%s@mesto.ua' % username, username=username)
        if created:
            random_user = User.objects.filter(ads_count__gt=500, first_name__isnull=False).order_by('?').first()

            user.date_joined = datetime.datetime.today() - datetime.timedelta(days=random.randint(10, 90))
            user.first_name = random_user.first_name
            user.last_name = random_user.last_name
            user.city = random_user.city
            user.save()

            phone, created = Phone.objects.get_or_create(number='3844200000%s' % index)
            UserPhone(user=user, phone=phone, order=1).save()

            # создаем объявления риелторам
            for i in xrange(random.randint(2, 13)):
                ad = self.generate_ad(user)
                PhoneInAd(phone=phone, basead=ad, order=1).save()

            print 'create user %d with %s ads' % (user.id, user.ads.count())


        return user

    # У всех риелторов есть статистика на 3 месяца по всем параметрам (причем у всех она разная)
    def generate_stats(self, user, force=False):
        if force:
            Stat.objects.filter(user=user).delete()

        last_stat = Stat.objects.filter(user=user).order_by('-date').last()

        stat_fields = ['new_properties', 'active_properties', 'paid_properties', 'money_spent', 'entrances', 'ad_views',
                      'ad_contacts_views', 'plan_first', 'plan_other']
        stat_as_dict = {key: last_stat.__dict__[key] if last_stat else 0 for key in stat_fields}

        day = user.date_joined
        while day < datetime.datetime.today():
            day += datetime.timedelta(days=1)

            # вероятность нормального человека, который отдыхает в выходные
            if day.weekday() > 4 and random.randrange(100) < 40:
                entrances = 0
            else:
                entrances = random.randint(1, 5)
            stat_as_dict['entrances'] = entrances

            # добавление объявлений
            new_properties = 0
            if entrances and random.randrange(100) < 50:
                new_properties = random.randint(0, 15)
                if new_properties:
                    stat_as_dict['entrances'] += random.randint(0, 5)

            stat_as_dict['new_properties'] = new_properties
            stat_as_dict['active_properties'] += new_properties

            # истекшие или деактивированные объявлени
            if random.randrange(100) < 30 and stat_as_dict['active_properties'] > 2:
                stat_as_dict['active_properties'] *= random.uniform(0.85, 1) # теряет до 30% активных объявлений

            paid_properties = random.randint(0, 1) if entrances else 0
            stat_as_dict['paid_properties'] += paid_properties
            stat_as_dict['money_spent'] += paid_properties * 15

            # окончившееся платное размещение
            if random.randrange(100) < 20 and stat_as_dict['paid_properties'] > 2:
                stat_as_dict['paid_properties'] -= random.randint(0, 2)

            # просмотры объявлений
            ad_views = stat_as_dict['active_properties'] * random.uniform(0.1, 0.5)
            stat_as_dict['ad_views'] = ad_views
            stat_as_dict['ad_contacts_views'] = ad_views * random.uniform(0.1, 0.3)

            # активированные и деактивируем пакеты
            if not stat_as_dict['plan_first'] and not stat_as_dict['plan_other'] and random.randrange(100) < 20:
                stat_as_dict[random.choice(['plan_first', 'plan_other'])] += 1
            if stat_as_dict['plan_first'] and random.randrange(100) < 10:
                stat_as_dict['plan_first'] -= 1
            if stat_as_dict['plan_other'] and random.randrange(100) < 10:
                stat_as_dict['plan_other'] -= 1

            stat = Stat.objects.get_or_create(user=user, date=day, defaults=stat_as_dict)

    def generate_leads_and_tasks(self, user, force=False):
        first_names = [u'Вадим', u'Матвей', u'Александр', u'Прохор', u'Николай', u'Семён', u'Глеб', u'Руслан', u'Алексей ', u'Егор', u'Валентин', u'Александр', u'Константин', u'Степан', u'Эрнст', u'Казимир', u'Богдан', u'Мстислав', u'Зиновий', u'Богдан', u'Владислав', u'Мир', u'Серафим', u'Глеб', u'Егор', u'Владлен', u'Сергей', u'Сергей', u'Алексей ', u'Артём']
        last_names = [u'Энговатов', u'Лобан', u'Яшвили', u'Пашков', u'Овсов', u'Гуринов', u'Лобов', u'Измайлов', u'Волынкин', u'Крутой', u'Никишов', u'Шапиро', u'Цаплин', u'Лавров', u'Монаков', u'Ельцин', u'Пургин', u'Посохов', u'Кярбер', u'Попырин', u'Ольховский', u'Быков', u'Федотов', u'Карташов', u'Катаев', u'Блок', u'Рыжанов', u'Колокольцов', u'Колесов']
        texts_for_message = [u'В какое время можно провести осмотр?', u'Какое состояние квартиры?', u'вы действительно хотите продать эту квартиру за такую цену?', u'Ипотека возможна?', u'готов купить прямо сейчас за наличные, но со скидкой 30000 грн', u'Не могу до вас дозвониться', u'Сколько собственников у квартиры?', u'Прямая продажа?', u'Почему так дорого?']
        realtor = user.get_realtor()
        leads_from_ad = 0

        if force:
            realtor.leads.all().delete()
            realtor.tasks.all().delete()
            Message.objects.filter(to_user__email__contains='user4demo').delete()
            Message.objects.filter(from_user__email__contains='user4demo').delete()

        # ~30 лидов (с разной степенью заполненности инфы и истории)
        for index in xrange(30):

            # 5 диалогов с юзерами (в тч 1 или 2 непрочитанных сообщения)
            if random.randrange(100) < 50 and leads_from_ad < 5:
                leads_from_ad += 1

                ad = user.ads.order_by('?').first()
                message = Message(basead=ad, to_user=user)
                message.from_user = User.objects.filter(email__contains='user4demo').order_by('?').first()
                message.readed = True

                for i in xrange(0, 2):
                    message.id = None
                    message.time = datetime.datetime.now() - datetime.timedelta(seconds=random.randint(60*24, 60*24*30))
                    message.text = random.choice(texts_for_message)
                    if message.readed:
                        message.readed = random.randrange(100) < 50
                    message.save()

                lead = Lead.objects.get(owner=realtor, user=message.from_user)
                if random.randrange(100) < 30:
                    lead.phone = message.from_user.phones.first().number
                if random.randrange(100) < 30:
                    lead.email = message.from_user.email
                if random.randrange(100) < 30:
                    lead.label = random.choice(dict(LEAD_LABELS[1:]).keys())
                lead.save()
            else:
                lead = Lead.objects.create(owner=realtor, phone='38442000%d' % random.randrange(100,1000),
                     name=u'%s %s' % (random.choice(first_names), random.choice(last_names)))

                if random.randrange(100) < 30:
                    lead.email = '%s%s@%s' % (slugify(lead.name), random.randint(60,95), random.choice(['ukr.net', 'gmail.com', 'mail.ru']))
                if random.randrange(100) < 70:
                    lead.label = random.choice(dict(LEAD_LABELS[1:]).keys())
                lead.save()

        # 3 встречи в календаре на будущее, 1 просроченная.
        for i in xrange(8):
            task = Task(owner=realtor, lead=lead, basead=lead.basead)
            task.lead = realtor.leads.order_by('?').first()
            task.start = datetime.datetime.now().replace(hour=random.randint(8, 18), minute=0) + datetime.timedelta(days=random.randint(-2,4))
            task.end = task.start  + datetime.timedelta(hours=1)
            task.name = random.choice([u'забрать ключи', u'показ квартиры', u'составление договора', u'регистрация квартиры'])
            task.save()
