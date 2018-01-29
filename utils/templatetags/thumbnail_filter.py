# coding: utf-8
from django import template
from utils.thumbnail import get_lazy_thumbnail, get_options

register = template.Library()


@register.filter
def thumbnail(file_, arguments_string):
    arguments = arguments_string.split(',')
    size = arguments.pop(0)
    if 'x' not in size:
        size = '{0}x{0}'.format(size)
    
    arguments = dict(x.split('=') for x in arguments)
    return get_lazy_thumbnail(file_, size, **get_options(size, 'nocrop' in arguments))


@register.filter
def thumbnail_alias(photo, alias):
    return photo.smart_thumbnail(alias)

