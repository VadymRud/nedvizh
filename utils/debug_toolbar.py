# coding: utf-8
from django.conf import settings

# отличается от оригинала (debug_toolbar.middleware.show_toolbar) тем, что нет проверки на INTERNAL_IPS
def show_toolbar(request):
    if request.is_ajax():
        return False

    return bool(settings.DEBUG)

