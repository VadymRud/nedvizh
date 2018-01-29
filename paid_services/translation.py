from modeltranslation.translator import translator, TranslationOptions
from paid_services.models import Plan

class PlanTranslationOptions(TranslationOptions):
    fields = ('name',)

translator.register(Plan, PlanTranslationOptions)
