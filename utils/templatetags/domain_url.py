# coding=utf-8
from django.template import Library
from django_hosts.resolvers import reverse

register = Library()

@register.simple_tag
def domain_url(name, *args, **kwargs):
    return reverse(name, args=args, kwargs=kwargs)

