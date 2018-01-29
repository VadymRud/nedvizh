# coding: utf-8
import pynliner
from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.utils import translation
from django.db.models import Q

from ad.models import Region
from custom_user.models import User
from django.utils.translation import ugettext_lazy as _


class Command(BaseCommand):
    help = 'Sends mails about specific seminar'

    def add_arguments(self, parser):
        parser.add_argument('--test-users', dest='test_users', nargs='+', type=int)
        parser.add_argument('--start-from-user', dest='start_from_user', nargs='?', type=int)
        parser.add_argument('--seminar-id', dest='seminar_id', type=str)
        parser.add_argument('--region-id', dest='region_id', type=int)
        parser.add_argument('--translation', dest='translation', nargs='+', type=str, default='ru')

    def handle(self, **options):
        if 'seminar_id' not in options or not options['seminar_id']:
            print 'Invalid Seminar ID'
            return
        else:
            options['seminar_id'] = options['seminar_id'].rjust(3, '0')

        if 'region_id' not in options or not options['region_id']:
            print 'Invalid Region ID'
            return

        translation.activate(options['translation'])

        subject = u'Приглашаем на тренинг-семинар 27 сентября в г Одесса'

        if 'test_users' in options and options['test_users']:
            users_email = set(User.objects.filter(id__in=options['test_users']).values_list('email', flat=True))
        else:
            regions_id = Region.objects.get(id=options['region_id']).get_children_ids()

            users_email_extended = ["vivalo78@mail.ru", "Larisa40239@ya.ru", "maristella.apartment@gmail.com", "titul27@i.ua", "professor.chernomor@gmail.com", "anikagamma@gmail.com",
                "lobachova.an@gmail.com", "smsarenda@mail.ru", "snata68@ukr.net", "moisa54@mail.ru", "bly999@yandex.ru", "c0999465547@gmail.com", "Demon96121@gmail.com", "valentina_ru@ukr.net",
                "tamara099@mail.ru", "n0975606808@yandex.com", "7011520@mail.ru", "odessa.arenda8877@mail.ru", "kanivichenko2014@gmail.com", "7030242@mail.ru", "mihail_semenuk@mail.ru",
                "Larisa40239@ya.ru", "redspartak15@mail.ru", "kvartal3016@mail.ru", "titul27@i.ua", "poiskdoma.od@gmail.com", "ks_skleynova@mail.ru", "parlament.evgen@gmail.com",
                "talisman2001@ukr.net", "favoryt_odessa@mail.ru", "7986065@gmail.com", "alenyushka@mail.ru", "mandrihenko@ukr.net", "kanivichenko2014@gmail.com", "dvalera-61@mail.ru",
                "ironyura2010@gmail.com", "lobachova.an@gmail.com", "nataly_kiriluk@mail.ru", "mikasa18@ukr.net", "nataly_kiriluk@mail.ru", "nataly_kiriluk@mail.ru", "kvartal3016@mail.ru",
                "zhmuyda@mail.ru", "Zinaida-mackiv@rambler.ru", "ulia12051951@ukr.net", "nadin2281@mail.ru", "angelika101@MAIL.RU", "ods.ua@i.ua", "dvalera-61@mail.ru", "5212131@ukr.net",
                "70395626@mail.ru", "7005025@mail.ru", "lana8888li@ukr.net", "2227735@ukr.net", "2227735@ukr.net", "2227735@ukr.net", "Urickayat@mail.ru", "Urickayat@mail.ru", "Urickayat@mail.ru",
                "nedvizhimost_odessa@mail.ru", "Urickayat@mail.ru", "jukar1900@gmail.com", "v.tarasevich_88@mail.ru", "oseninaelena@mail.ru", "lider_a@mail.ua", "garant59a@ukr.net",
                "ilonakiyan@ukr.net", "kiriljuk_nl@mail.ru", "0982899058@mail.ru", "evropa-letters@mail.ru", "valik1985@bk.ru", "nataly_kiriluk@mail.ru", "kifalena@ukr.net.ua", "okssana268@mail.ru",
                "olika_83@ukr.net", "ocenochka@rambler.ru", "reklama@evropa.od.ua", "ikt94@mail.ru", "poiskdoma.od@gmail.com", "ksana19@meta.ua", "kiriljuk_nl@mail.ru", "n0975606808@yandex.com",
                "natala08@ukr.net", "assol56@mail.ru", "kskd08@rambler.ru", "0793059@gmail.com", "odessa.makler@yandex.ru", "kanivichenko2014@gmail.com", "nataliya12b@yandex.ua",
                "favoryt_odessa@mail.ru", "ironyura2010@gmail.com", "nura-a@ukr.net", "valik1985@bk.ru", "delta-odessa@yandex.ru", "delta-odessa@yandex.ru", "dzu-@ukr.net", "tulechka@ukr.net",
                "bereg-od@mail.ru", "Rent4242@mail.ru", "odessa.arenda8877@mail.ru", "netinger.nata@gmail.com", "dsaodessa@gmail.com", "zerro39@ukr.net", "tanya_09t@mail.ru", "reklama@premier.od.ua",
                "futury@list.ru", "7030242@mail.ru", "lenabidz@gmail.com", "7062021@gmail.com", "7990914@mail.ru", "lenabidz@gmail.com", "marina.podgora@mail.ru", "moisa54@mail.ru", "RAS.55@mail.ru", "favoryt_odessa@mail.ru", "kvartal3016@mail.ru", "kanivichenko2014@gmail.com", "zerro39@ukr.net", "odessa.arenda8877@mail.ru", "kiriljuk_nl@mail.ru", "alekobera@mail.ru",
                "vip-kvartira@inbox.ru", "elena7020519@rambler.ru", "favoryt_odessa@mail.ru", "alekobera@mail.ru", "katerina-2010@ukr.net", "kanivichenko2014@gmail.com", "0981536659@ukr.net",
                "evropa-letters@mail.ru", "titul27@i.ua", "varvara.semenchenko@rambler.ru", "groza.expert@gmail.com", "fart.ua.82@mail.ru", "valentina_rent@mail.ru", "valentina_rent@mail.ru",
                "lyubov.f.s@gmail.com", "favoryt_odessa@mail.ru", "7435355@ro.ru", "bjuro1900@meta.ua", "moisa54@mail.ru", "kanivichenko2014@gmail.com", "rollsy2000@gmail.com",
                "mayor72od@mail.ru", "kanivichenko2014@gmail.com", "favoryt_odessa@mail.ru", "varvara.semenchenko@rambler.ru", "sotulenko-anastasia@rambler.ru", "dovira_31@mail.ua",
                "favoryt_odessa@mail.ru", "7989310@mail.ru", "slando90@gmail.com", "7435355@ro.ru", "turkakif.tdm@gmail.com", "goserp@ukr.net", "favoryt_odessa@mail.ru", "lar-ua@mail.ru",
                "dvalera-61@mail.ru", "ironyura2010@gmail.com", "titul27@i.ua", "kiriljuk_nl@mail.ru", "anikagamma@gmail.com"]

            users_filter = Q(ads_count__gt=0, ads__region__in=regions_id) | Q(email__in=users_email_extended)
            users_email = set(User.objects.filter(email__gt='', subscribe_news=True).filter(users_filter).values_list('email', flat=True))

        print '%d emals total' % len(users_email)
        for user_email in users_email:
            print 'user email %s' % user_email
            content = render_to_string('mail/mailing/mail_about_seminar_%s.jinja.html' % options['seminar_id'], {})
            content_with_inline_css = pynliner.fromString(content)
            message = EmailMessage(subject, content_with_inline_css, settings.DEFAULT_FROM_EMAIL, [user_email])
            message.content_subtype = 'html'
            message.send()
