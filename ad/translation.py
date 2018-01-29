from modeltranslation.translator import translator, TranslationOptions
from ad.models import Region, DealType, Facility, Rules, SubwayLine, SubwayStation


class RegionTranslationOptions(TranslationOptions):
    fields = ('name', 'name_declension', 'old_name', 'old_name_declension')


class FacilityTranslationOptions(TranslationOptions):
    fields = ('name',)

class DealTypeTranslationOptions(TranslationOptions):
    fields = ('name',)


class RulesTranslationOptions(TranslationOptions):
    fields = ('name',)


class SubwayLineTranslationOptions(TranslationOptions):
    fields = ('name',)


class SubwayStationTranslationOptions(TranslationOptions):
    fields = ('name',)


translator.register(SubwayLine, SubwayLineTranslationOptions)
translator.register(SubwayStation, SubwayStationTranslationOptions)
translator.register(Region, RegionTranslationOptions)
translator.register(DealType, DealTypeTranslationOptions)
translator.register(Facility, FacilityTranslationOptions)
translator.register(Rules, RulesTranslationOptions)