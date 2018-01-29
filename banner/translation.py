from modeltranslation.translator import translator, TranslationOptions
from banner.models import Banner

class BannerTranslationOptions(TranslationOptions):
    fields = ('image', 'image_bg')

translator.register(Banner, BannerTranslationOptions)
