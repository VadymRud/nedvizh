# coding: utf-8

import boto3
import datetime
import json

from django.conf import settings
from django.core.management.base import BaseCommand

from custom_user.models import User


class Command(BaseCommand):
    help = 'Receive information about bounces and complains from AmazonSES. ' \
           'Removing user subscription on specific emails'

    def handle(self, **options):
        print datetime.datetime.now()

        sqs = boto3.client(
            'sqs', region_name=settings.AWS_SQS_REGION_NAME, aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )

        messages = sqs.receive_message(QueueUrl=settings.AWS_SQS_QUEUE_URL, MaxNumberOfMessages=10, WaitTimeSeconds=10)
        while messages.get(u'Messages', []):
            entries = []
            emails = set()
            for position, message in enumerate(messages[u'Messages']):
                # Подготавливаем данные для удаления прочитанных сообщений
                entries.append({
                    'Id': '{:d}'.format(position),
                    'ReceiptHandle': message[u'ReceiptHandle']
                })

                # Разбираем и сообщения с необходимыми типами обрабатываем
                message = json.loads(message[u'Body'])
                message['Message'] = json.loads(message['Message'])
                if message['Message']['notificationType'] == 'Bounce':
                    bounce = message['Message']['bounce']
                    if bounce['bounceType'] in ['Permanent', 'Undetermined']:
                        for recipient in bounce['bouncedRecipients']:
                            emails.add(recipient['emailAddress'])

                elif message['Message']['notificationType'] == 'Complaint':
                    complaint = message['Message']['complaint']
                    if complaint['complaintFeedbackType'] not in ['not-spam']:
                        for recipient in complaint['complainedRecipients']:
                            emails.add(recipient['emailAddress'])

            # Отписываем пользователей
            if emails:
                print u'Unsubscribe emails: {:s}'.format(u', '.join(emails))
                User.objects.filter(email__in=emails).update(subscribe_info=False, subscribe_news=False)

            # Удаляем сообщения
            # Ответ от AmazonSQS не обрабатывается, предполагается удаление сообщений всегда успешно
            if entries:
                sqs.delete_message_batch(QueueUrl=settings.AWS_SQS_QUEUE_URL, Entries=entries)

            # Получаем новую порцию сообщений
            messages = sqs.receive_message(
                QueueUrl=settings.AWS_SQS_QUEUE_URL, MaxNumberOfMessages=10, WaitTimeSeconds=10
            )
