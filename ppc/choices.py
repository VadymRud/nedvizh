# coding: utf-8

from django.utils.translation import ugettext_lazy as _

DEAL_TYPE_CHOICES = (
    ('rent', _(u'аренда')),
    ('rent_daily', _(u'посуточная аренда')),
    ('sale', _(u'продажа')),
    ('newhomes', _(u'новостройки')),
)

LEAD_GENERATION_CHOICES = (
    ('ads', _(u'Объявления')),
    ('newhomes', _(u'Новостройки'))
)

LEAD_PRICES = {
    'call': {
        'newhomes': {'high': 80},
        'sale': {'low': 20, 'medium': 20, 'high': 25},
        'rent': {'low': 10, 'medium': 10, 'high': 15},
        'rent_daily': {'low': 20, 'medium': 20, 'high': 25},
        'other': {'low': 20, 'medium': 20, 'high': 25}
    },
    'callrequest': {
        'newhomes': {'high': 50},
        'sale': {'low': 15, 'medium': 15, 'high': 20},
        'rent': {'low': 5, 'medium': 5, 'high': 10},
        'rent_daily': {'low': 15, 'medium': 15, 'high': 20},
        'other': {'low': 10, 'medium': 10, 'high': 15}
    },
}

COMPLAINT_CHOICES = (
    ('awaiting', _(u'рассмативается')),
    ('rejected', _(u'отклонена')),
    ('accepted', _(u'принята')),
)
