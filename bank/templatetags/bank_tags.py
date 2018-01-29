# coding: utf-8
from django.template import Library
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _
from django_hosts.resolvers import reverse

from utils import gtm

import re
import json

register = Library()


@register.assignment_tag
def make_gtm_data(request):
    return json.dumps(gtm.make_gtm_data(request))


@register.filter(is_safe=True)
def hide_contacts(string, target=''):
    return mark_safe(
        u'<a title="' + _(u'Узнать номер') + u'" class="show-contacts" data-target="%s">%s%s</a>' % (
            target, string[:3], re.sub(r"[\da-zA-Z]", "*", string[3:])
        ))


@register.assignment_tag(takes_context=True)
def get_menu(context):
    menu = [
        [_(u'Жильё'), '/residential/', 'first'],
        [_(u'Земля'), '/land/', ''],
        [_(u'Коммерческие объекты'), '/commercial/', ''],
        [_(u'Банки'), '/banks/', 'last']
    ]

    for item in menu:
        if item[1] in context.request.path:
            item[2] += ' active'

    return menu

@register.simple_tag
def bank_domain_url(name, *args, **kwargs):
    return reverse(name, host='bank', args=args, kwargs=kwargs)

