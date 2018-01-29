# coding: utf-8
import pynliner
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.urlresolvers import reverse
from django.template.loader import render_to_string
from django.utils import translation
from django.utils.translation import ugettext_lazy as _
from registration.models import RegistrationProfile


# пропатченный метод RegistrationProfile.send_activation_email для возможности
# пост-обработки отрендеренного html при отправке письма активации, например, pynliner.fromString(content)
def patched_send_activation_email(self, site, request=None):
    # скопировано из оригинального метода:
    ctx_dict = {
        'user': self.user,
        'activation_key': self.activation_key,
        'expiration_days': settings.ACCOUNT_ACTIVATION_DAYS,
        'site': site,
    }

    translation.activate(request.LANGUAGE_CODE)
    subject = _(u'Активация аккаунта на сайте %s') % site.name
    message_txt = render_to_string('registration/activation_email.txt', ctx_dict)
    message_html = pynliner.fromString(render_to_string('registration/activation_email.jinja.html', ctx_dict))

    email_message = EmailMultiAlternatives(subject, message_txt, settings.DEFAULT_FROM_EMAIL, [self.user.email])
    email_message.attach_alternative(message_html, 'text/html')
    email_message.send()


def patch():
    RegistrationProfile.send_activation_email = patched_send_activation_email
