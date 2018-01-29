from django.test import TestCase, RequestFactory

from django_hosts.resolvers import reverse

from utils.middleware import TrafficSourceMiddleware

class TrafficSourceRefererTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_traffic_source(self):
        for referer, traffic_source in (
            ('//google.ua', 'seo'),
            ('//www.yandex.ru', 'seo'),
            ('//trovit.com/test/?test=1', 'trovit'),
            ('//www.trovit.com', 'trovit'),
            ('//lun.ua/', 'lun'),
            ('//luna.ua', 'other'),
            ('//example.com', 'other'),
            (reverse('index', host_args=['kiev']), 'direct'),
            ('//mitula.com', 'mitula'),
            ('//mitula.ru/', 'mitula'),
            ('//mitula.com.ua', 'mitula'),
            ('//facebook.com/', 'facebook'),
            ('//vk.com/mestoua/', 'vk.com'),
        ):

            request = self.factory.get('/', HTTP_REFERER=referer)
            middleware = TrafficSourceMiddleware()
            middleware.process_request(request)
            self.assertEqual(request.traffic_source, traffic_source)

