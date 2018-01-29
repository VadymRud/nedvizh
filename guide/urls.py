from django.conf.urls import url

import guide.views

urlpatterns = [
    url(r'^$', guide.views.index, name='index'),
    url(r'^(?P<category>news|events|places|must_know)/$', guide.views.category_list, name='category_list'),
    url(r'^(?P<category>news|events|places|must_know)/(?P<slug>[_a-zA-Z0-9\-\.]*)/$', guide.views.article_detail, name='article_detail'),
]

