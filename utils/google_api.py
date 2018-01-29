# coding: utf-8
import re
from django.conf import settings
import requests


class GoogleAPI(object):
    """
    Класс для работы с GoogleAPI

    Features:
    - Работа с YouTubeAPI: получение информации о видео
    - Работа с YouTubeAPI: загрузка дерева комментариев к видео
    """

    _api_host = None
    _api_url = None
    _api_params = {}
    _video_code = None
    video_info = {
        'thumbnail_url': '#',
        'duration': '00:00'
    }

    def __init__(self, *args, **kwargs):
        # Хост для подключения
        self._api_host = settings.GOOGLE_API_HOST

    def _send_request(self):
        """
        Отправляем запрос по получению данных
        :return:
        """

        # Основные параметры для работы с API
        self._api_params.update({
            'key': settings.GOOGLE_API_KEY
        })

        url = self._api_host + self._api_url
        response = requests.get(url, params=self._api_params)

        if response.status_code == 200:
            return response.json()

        else:
            raise Exception(u"Can't connect to host or URL error")

    @staticmethod
    def _prepare_duration_string(duration):
        """
        Приводим формат продолжительности к читаемому виду ISO 8601
        :param duration: String PT#M#S
        :return:
        """

        duration = duration.replace(u'PT', u'')
        duration = duration.replace(u'M', u':')
        duration = duration.replace(u'S', u'')

        return duration

    def youtube_get_video_code_from_embed(self, str_to_parse):
        """
        Получаем код видео, из embed-строки
        <iframe width="560" height="315" src="https://www.youtube.com/embed/jt3oAyK_IG8" frameborder="0" allowfullscreen></iframe>

        Или ссылки на видео
        http://youtube.com/watch?v=jt3oAyK_IG8

        :param str_to_parse: String to parse
        :return video_code: String
        """

        video_code_from_embed = re.findall(u'embed/(.*?)"', str_to_parse, re.IGNORECASE | re.UNICODE)
        video_code_from_url = re.findall(u'v=([a-zA-Z0-9_-]*)', str_to_parse, re.IGNORECASE | re.UNICODE)
        if video_code_from_embed:
            video_code = video_code_from_embed[0].split('?')[0]

        elif video_code_from_url:
            video_code = video_code_from_url[0]

        else:
            raise Exception(u'Video code not found. Please check embed or search algorythm')

        self._video_code = video_code

        return self._video_code

    def youtube_get_player(self, video_code=None, embed=None):
        """
        Получаем HTML код проигрывателя

        :param video_code: ID видео
        :param embed: Embed-код плеера или URL адрес
        :return:
        """

        # Работаем над определением ID видео
        if video_code:
            self._video_code = video_code

        elif embed is not None:
            self.youtube_get_video_code_from_embed(embed)

        else:
            raise Exception(u'Video code not found. Please check embed or search algorythm')

        self._api_url = '/youtube/v3/videos'

        # Получаем код плеера
        self._api_params = {
            'videoId': self._video_code,
            'id': self._video_code,
            'part': 'player'
        }
        response = self._send_request()
        self._api_params = {}

        player_info = response.get('items', None)
        if player_info:
            player = player_info[0][u'player'][u'embedHtml']

            return player

    def youtube_get_video_comments(self, video_code=None, embed=None, max_results=50, page_token=None):
        """
        Получаем комментарии видео

        :param video_code: ID видео
        :param embed: Embed-код плеера или URL адрес
        :return: dict
        """

        # Работаем над определением ID видео
        if video_code:
            self._video_code = video_code

        elif embed is not None:
            self.youtube_get_video_code_from_embed(embed)

        else:
            raise Exception(u'Video code not found. Please check embed or search algorythm')

        self._api_url = '/youtube/v3/commentThreads'

        # Получаем Thumbnail
        if 'id' in self._api_params:
            del self._api_params['id']

        self._api_params = {
            'videoId': self._video_code,
            'maxResults': max_results,
            'part': 'snippet'
        }

        if page_token is not None:
            self._api_params.update({
                'pageToken': page_token
            })

        response = self._send_request()

        return response

    def youtube_get_video_info(self, video_code=None, embed=None, get_statistic=False):
        """
        Получаем информацию о видео

        :param video_code: ID видео
        :param embed: Embed-код плеера или URL адрес
        :return: dict
        """

        # Работаем над определением ID видео
        if video_code:
            self._video_code = video_code

        elif embed is not None:
            self.youtube_get_video_code_from_embed(embed)

        else:
            raise Exception(u'Video code not found. Please check embed or search algorythm')

        # Зануляем базовую инфу
        self.video_info.update({
            'thumbnail_url': '#',
            'duration': '00:00',
            'view_count': 0
        })

        self._api_url = '/youtube/v3/videos'

        # Получаем Thumbnail
        self._api_params = {
            'id': self._video_code,
            'part': 'snippet'
        }
        response = self._send_request()

        thumbnail_info = response.get('items', None)
        if thumbnail_info:
            self.video_info.update({
                'thumbnail_url': thumbnail_info[0][u'snippet'][u'thumbnails'][u'high'][u'url']
            })

        # Получаем продолжительность видео
        self._api_params.update({
            'part': 'contentDetails'
        })
        response = self._send_request()
        duration_info = response.get('items', None)
        if duration_info:
            self.video_info.update({
                'duration': self._prepare_duration_string(duration_info[0][u'contentDetails'][u'duration'])
            })

        # Получаем количество просмотров
        if get_statistic:
            self._api_params.update({
                'part': 'statistics'
            })
            response = self._send_request()
            view_count_info = response.get('items', None)
            if view_count_info:
                self.video_info.update({
                    'view_count': view_count_info[0][u'statistics'][u'viewCount']
                })

        return self.video_info
