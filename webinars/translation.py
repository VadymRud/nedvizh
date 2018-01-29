from modeltranslation.translator import translator, TranslationOptions
from webinars.models import Webinar, Speaker


class WebinarTranslationOptions(TranslationOptions):
    fields = ('title', 'teaser', 'address', 'description', 'seo_title', 'seo_description', 'seo_keywords', 'city')

translator.register(Webinar, WebinarTranslationOptions)


class SpeakerTranslationOptions(TranslationOptions):
    fields = ('name', 'title')

translator.register(Speaker, SpeakerTranslationOptions)
