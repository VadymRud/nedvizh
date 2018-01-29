from modeltranslation.translator import translator, TranslationOptions
from profile.models import Notification

class NotificationTranslationOptions(TranslationOptions):
    fields = ('text',)

translator.register(Notification, NotificationTranslationOptions)

