# coding: utf-8
import datetime
from django.core.management.base import BaseCommand
from webinars.models import Webinar
from utils.google_api import GoogleAPI


class Command(BaseCommand):
    help = u'Обновление данных о прошедших вебинарах: кол-во просмотров, продолжительность'

    def handle(self, *args, **options):
        webinars = Webinar.objects.filter(is_published=True, finish_at__lte=datetime.datetime.now())
        for webinar in webinars:
            if webinar.video:
                gapi = GoogleAPI()
                video_info = gapi.youtube_get_video_info(embed=webinar.video, get_statistic=True)
                webinar.youtube_image = video_info['thumbnail_url']
                webinar.youtube_duration = video_info['duration']
                webinar.youtube_views_count = video_info['view_count']
                webinar.save()
