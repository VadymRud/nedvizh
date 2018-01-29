# coding=utf-8
import os
from django.core.management.base import BaseCommand
from django.conf import settings

from seo.models import TextBlock


class Command(BaseCommand):
    help = u'Импорт seo-текстов из файла region-text.txt'

    def handle(self, *args, **options):
        print self.help
        path = os.path.join(settings.BASE_DIR, 'region-text.txt')
        with open(path) as f:
            attrs = {'url': '', 'title': '', 'text':''}
            for line in f:
                line = line.decode('utf8').strip()
                if 'http' in line:
                    attrs['url'] = line
                    if '?' not in attrs['url']:
                        attrs['url'] = attrs['url'].strip('/') + '/'
                elif u'– Н2' in line:
                    attrs['title'] = line.replace(u"– Н2", "").strip()
                elif line:
                    attrs['text'] += u"<p>%s</p>\n" % line
                elif attrs and attrs.get('url') and attrs.get('text'):
                    textblock, created = TextBlock.objects.get_or_create(url=attrs['url'], defaults=attrs)
                    if not created:
                        textblock.text = attrs['text']
                        textblock.save()

                    print textblock, created
                    attrs = {'url': '', 'title': '', 'text':''}