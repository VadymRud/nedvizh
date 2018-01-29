from modeltranslation.translator import translator, TranslationOptions
from staticpages.models import Article, FAQCategory, FAQArticle, FAQBase, SimplePage, ContentBlock


class SimplePageTranslationOptions(TranslationOptions):
    fields = ('title', 'content', 'seo_title', 'seo_description')


class ContentBlockTranslationOptions(TranslationOptions):
    fields = ('content',)


class ArticleTranslationOptions(TranslationOptions):
    fields = ('name', 'title', 'content', 'description')


class FAQCategoryTranslationOptions(TranslationOptions):
    fields = ('title', 'seo_title', 'seo_description', 'seo_keywords')


class FAQArticleTranslationOptions(TranslationOptions):
    fields = ('title', 'seo_title', 'seo_description', 'seo_keywords', 'content', 'video')


translator.register(SimplePage, SimplePageTranslationOptions)
translator.register(ContentBlock, ContentBlockTranslationOptions)
translator.register(Article, ArticleTranslationOptions)
translator.register(FAQCategory, FAQCategoryTranslationOptions)
translator.register(FAQArticle, FAQArticleTranslationOptions)
