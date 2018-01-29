# coding=utf-8
from django.core.paginator import Paginator, Page, EmptyPage
from django.utils.functional import cached_property

class HandyPaginator(Paginator):
    def __init__(self, objects, per_page, request, per_page_variants=None, **kwargs):
        self.request = request
        self.current_page_number = int(request.GET.get('p', 1))

        # ограничение максимальной страницы для всех пользователей и плохих ботов
        if self.current_page_number > 500 and not request.is_customer and not request.is_search_engine \
                and not request.user.is_authenticated():
            raise Exception('Probably bot')

        self.cleaned_query_dict = request.GET.copy()
        self.cleaned_query_dict.pop('p', None)

        per_page = self._get_per_page_limit(per_page, per_page_variants)
        super(HandyPaginator, self).__init__(objects, per_page, **kwargs)

        self._set_current_page()
        self._set_truncated_page_range()

    # выставляется количество элементов на странице
    def _get_per_page_limit(self, per_page, per_page_variants):
        self.per_page_variants = per_page_variants

        if self.per_page_variants:
            default_per_page = per_page
            try:
                per_page = int(self.cleaned_query_dict.get('per_page', default_per_page))
            except (ValueError, TypeError):
                per_page = default_per_page
            if per_page not in self.per_page_variants:
                per_page = default_per_page
        return per_page

    # получаем объект Page со списком элементов на странице
    def _set_current_page(self):
        if self.current_page_number < 1 or self.current_page_number > self.num_pages:
            self.current_page_number = 1

        self.current_page = self.page(self.current_page_number)

    # заполняем строку пагинатора номерами страниц в виде " 1 ... 4 5 6 ... 444"
    def _set_truncated_page_range(self):
        gap = 2
        addition_compensation = 2
        if self.current_page_number > addition_compensation + 1 + gap:
            start = self.current_page_number - gap
            start_range_addition = [1, '...']
        else:
            start = 1
            start_range_addition = []
        if self.current_page_number < self.num_pages - addition_compensation - gap:
            end = self.current_page_number + gap + 1
            end_range_addition = ['...', self.num_pages]
        else:
            end = self.num_pages + 1
            end_range_addition = []
        self.truncated_page_range = start_range_addition + range(start, end) + end_range_addition

    def get_page_url(self, page):
        if page < 1:
            raise Exception('page < 1')

        url = self.request.build_absolute_uri(self.request.path)
        query_dict = self.cleaned_query_dict.copy()
        if page > 1:
            query_dict['p'] = page
        if query_dict:
            url = url + '?' + query_dict.urlencode()

        return url


class AdPaginator(HandyPaginator):
    offset_hack = True

    def __init__(self, objects, per_page, request, per_page_variants=None, offset_hack=True, **kwargs):
        self.offset_hack = offset_hack
        super(AdPaginator, self).__init__(objects, per_page, request, per_page_variants, **kwargs)

    def _set_truncated_page_range(self):
        gap = 2
        addition_compensation = 2
        if self.current_page_number > addition_compensation + 1 + gap:
            start = self.current_page_number - gap
            start_range_addition = [1, '...']
        else:
            start = 1
            start_range_addition = []
        if self.current_page_number < self.num_pages - addition_compensation - gap:
            end = self.current_page_number + gap + 1
            end_range_addition = ['...', self.num_pages]
        else:
            end = self.num_pages + 1
            end_range_addition = []
        self.truncated_page_range = start_range_addition + range(start, end) + end_range_addition

    @cached_property
    def count(self):
        """
        Returns the total number of objects, across all pages.
        """
        #### в оригинале (django-1.10.6)
        # try:
            # return self.object_list.count()
        # except (AttributeError, TypeError):
            # # AttributeError if object_list has no count() method.
            # # TypeError if object_list.count() requires arguments
            # # (i.e. is of type list).
            # return len(self.object_list)
        #### наш вариант
        return None

    @cached_property
    def num_pages(self):
        """
        Returns the total number of pages.
        """
        if self.count == 0 and not self.allow_empty_first_page:
            return 0
        #### в оригинале (django-1.10.6)
        # hits = max(1, self.count - self.orphans)
        # return int(ceil(hits / float(self.per_page)))
        #### наш вариант
        return self.current_page_number + (len(self.object_list_prefetched) - 1) // self.per_page

    def _set_current_page(self):
        self.prefetch_object_list()
        self.current_page = self.page(self.current_page_number)

    def prefetch_object_list(self):
        if self.offset_hack:
            page = (self.current_page_number - 1) % 500 + 1
            bottom = (page - 1) * self.per_page
        else:
            bottom = (self.current_page_number - 1) * self.per_page
        top = bottom + self.per_page * 3
        self.object_list_prefetched = list(self.object_list[bottom:top])

    def page(self, number):
        return AdPage(self.object_list_prefetched[:self.per_page], number, self)



class AdPage(Page):
    def __init__(self, object_list, number, paginator):
        object_list_extended = list(object_list)
        object_list = object_list_extended[:paginator.per_page]

        paginator.num_page = number + len(object_list_extended) // paginator.per_page

        super(AdPage, self).__init__(object_list, number, paginator)
