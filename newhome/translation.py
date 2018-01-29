from modeltranslation.translator import translator, TranslationOptions
from newhome.models import Newhome, LayoutNameOption


class NewhomeTranslationOptions(TranslationOptions):
    fields = ('name', 'keywords', 'seller', 'developer')

translator.register(Newhome, NewhomeTranslationOptions)


class LayoutNameOptionTranslationOptions(TranslationOptions):
    fields = ('name',)

translator.register(LayoutNameOption, LayoutNameOptionTranslationOptions)
