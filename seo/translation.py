from modeltranslation.translator import translator, TranslationOptions
from ad.models import Region, Facility, Rules
from seo.models import SEORule, SEOCachedPhrase


class SEORuleTranslationOptions(TranslationOptions):
    fields = ('crosslink_header', 'h1', 'title', 'keywords', 'description')

translator.register(SEORule, SEORuleTranslationOptions)


class SEOCachedPhraseTranslationOptions(TranslationOptions):
    fields = ('phrase',)


translator.register(SEOCachedPhrase, SEOCachedPhraseTranslationOptions)
