# coding: utf-8
import pynliner
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from django.core.files import File
from django.core.cache import cache
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import translation
from django.utils.translation import ugettext_lazy as _

from ppc.models import ProxyNumber, Call, ActivityPeriod, LeadGeneration, AsteriskLeadNumber
from callcenter.models import AsteriskCdr
from utils.email import make_ga_pixel_dict, make_utm_dict

from tempfile import TemporaryFile
import traceback
import datetime
import re


class Command(BaseCommand):
    sftp = None

    def handle(self, *args, **options):
        print '--- {} ---'.format(datetime.datetime.now())
        error_text = None

        # подключение к sftp
        try:
            import paramiko
            try:
                transport = paramiko.Transport((settings.MESTO_ASTERISK_SSH['host'], settings.MESTO_ASTERISK_SSH['port']))
                transport.connect(username=settings.MESTO_ASTERISK_SSH['username'], password=settings.MESTO_ASTERISK_SSH['password'])
                self.sftp = paramiko.SFTPClient.from_transport(transport)
            except paramiko.ssh_exception.SSHException:
                print 'no connection to asterisk server via SSH'
        except ImportError:
            print 'library paramiko not found'

        '''
        # Синхронизация с Asterisk отключена, т.к. перешли на Ringostat.
        # Код оставлен на всякий случай, если вернемся обратно к старой телефонии
        try:
            # проверяем появились ли новые номера для переадресаций
            self.update_proxynumbers_list()

            # обновление данных по звонкам на номера pay per call
            self.sync_call_data_from_asterisk()
        except Exception:
            print 'errors with asterisk database: %s' % traceback.format_exc()

            if not cache.get('notification_about_asterisk_down_has_sent'):
                from django.core.mail import send_mail
                send_mail(u'Mesto.UA: Проблемы с подключением к БД Asterisk', u'Аттеншен! Сабж.\nОшибка: %s' %  traceback.format_exc(),
                          settings.DEFAULT_FROM_EMAIL, ['zeratul268@gmail.com'], fail_silently=False)
                cache.set('notification_about_asterisk_down_has_sent', True, 60*60*3)
        '''

        # проверяем наличие оплаты за выденные номера
        for leadgeneration in LeadGeneration.objects.filter(dedicated_numbers=True):
            leadgeneration.check_dedicated_numbers()

        # проверка баланса агентств для рассылки уведомлений и отключения объявлений
        # у застройщика отключаются объекты при недостатке средств
        self.check_lead_type()

        # освобождение номеров, у которых прошел срок блокирования/заморозки
        self.free_holded_numbers()

        # выкачиваем записи разговоров
        self.download_records_from_ringostat()


    @staticmethod
    def download_records_from_ringostat():
        calls = Call.objects.filter(call_time__gt=datetime.datetime.now() - datetime.timedelta(minutes=30), duration__gt=0, recordingfile='')
        for call in calls:
            record_url = cache.get('call%d-record' % call.pk)
            if record_url:
                call.download_record(record_url)

    @staticmethod
    def check_lead_type():
        # условие .exclude(user__leadgenerationbonuses__end=None) пропускает бонусную лидогенерацию на 10 звонков/лидов
        # для этого бонуса отключение происходит в paid_services.models.leadgeneration_bonus, а уведомления о балансе не нужны
        for activityperiod in ActivityPeriod.objects.filter(end=None):
            user = activityperiod.user
            if activityperiod.lead_type == 'ads' and user.leadgenerationbonuses.filter(end=None).exists():
                continue

            if user.get_balance() < 10:
                print 'Balance < 10. Stop leadgeneration period %d' % activityperiod.id
                activityperiod.stop()

                # смс-сообщение или пуш-уведомление в приложении
                notification_content = u'Уважаемый пользователь, на Вашем балансе %d грн, ' \
                                       u'услуга Оплата за звонок приостановлена. ' \
                                       u'Пополните баланс и продолжайте получать звонки!' % user.get_balance()
                user.send_notification(notification_content, sms_numbers_limit=1)

                if user.subscribe_info:
                    translation.activate(user.language)
                    subject = _(u'Вы не можете получать звонки')
                    utm = make_utm_dict(utm_campaign='popolnenie_balansa', utm_content='klienti_s_ppc')
                    content = render_to_string(
                        'ppc/mail/money_not_enough.jinja.html',
                        {
                            'utm': utm,
                            'ga_pixel': make_ga_pixel_dict(user, utm)
                        }
                    )
                    content_with_inline_css = pynliner.fromString(content)
                    message = EmailMessage(subject, content_with_inline_css, settings.DEFAULT_FROM_EMAIL, [user.email])
                    message.content_subtype = 'html'
                    message.send()

    @staticmethod
    def free_holded_numbers():
        for proxynumber in ProxyNumber.objects.filter(hold_until__lt=datetime.datetime.now()):
            proxynumber.user = None
            proxynumber.deal_type = None
            proxynumber.hold_until = None
            proxynumber.save()

            print 'Proxynumber %s became free' % proxynumber.number


    def sync_call_data_from_asterisk(self):
        proxynumbers = ProxyNumber.objects.filter(provider='local')

        # в их базе входящие номера заведены в формате 442286898 (без 380)
        cdr_numbers = [re.sub(r'^380', '', proxynumber.number) for proxynumber in proxynumbers]

        for cdr in AsteriskCdr.objects.using('asterisk').filter(dst__in=cdr_numbers, userfield__startswith='leadgen',
                                                        calldate__gt=datetime.datetime.now() - datetime.timedelta(hours=48)):
            call_data = cdr.userfield.split('_')
            if not Call.objects.filter(uniqueid1=cdr.uniqueid).exists():
                proxynumber = ProxyNumber.objects.get(number='380%s' % cdr.dst)

                if not proxynumber.user:
                    print( u"Haven't found user for number %s. Userfield: %s"
                           % (proxynumber.number, cdr.userfield)).encode('utf-8')
                    continue
                elif proxynumber.hold_until:
                    print (u"Proxynumber %s belonged to user %s, number is held until %s. Userfield: %s" %
                           (proxynumber.number, proxynumber.user, proxynumber.hold_until, cdr.userfield)).encode('utf-8')
                    continue

                call = Call(proxynumber=proxynumber, call_time=cdr.calldate, uniqueid1=cdr.uniqueid, callerid1=cdr.src, user2=proxynumber.user,
                            deal_type=proxynumber.deal_type)

                # ID объекта введенного при звонке
                if call_data[2].isdigit():
                    call.object_id = call_data[2]

                # номер ответившего риелтора
                if call_data[1].isdigit():
                    call.callerid2 = call_data[1]

                if cdr.disposition not in ['NO ANSWER', 'BUSY'] and call.callerid2:
                    call.duration = cdr.billsec

                # для отвеченных звоноков выкачивание записи и сохранение в recordingfile
                if call.duration > 0:
                    filename = '%s.wav' % call.uniqueid1
                    with TemporaryFile() as tmpfile:
                        try:
                            if self.sftp:
                                self.sftp.getfo('/records/' + filename, tmpfile)
                                call.recordingfile.save(filename, File(tmpfile), save=False)
                                print 'downloaded', filename
                            else:
                                print 'Trying to get file from FTP: /records/%s' % filename
                        except IOError:
                            print 'no file', filename

                call.save()
                print 'Call #%s created' % call.pk

    def update_proxynumbers_list(self):
        for leadnumber in AsteriskLeadNumber.objects.using('asterisk').all():
            proxynumber, created = ProxyNumber.objects.get_or_create(number='380{}'.format(leadnumber.number))
            if created:
                print 'Proxynumber {} created'.format(leadnumber.number)
