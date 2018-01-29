from django.conf.urls import url

import paid_services.views
import ppc.views

urlpatterns = [
    url(r'^publication/$', paid_services.views.index, name='index'),
    url(r'^publication/lead/$', ppc.views.lead, name='lead'),
    url(r'^publication/vips/$', paid_services.views.vips, name='vips'),
    url(r'^publication/lead/activate/$', ppc.views.lead_activate, name='lead_activate'),
    url(r'^publication/plans/$', paid_services.views.plans, name='plans'),
    url(r'^publication/international/$', paid_services.views.international, name='international'),
    url(r'^extra/$', paid_services.views.vips, name='extra_index'),
    url(r'^extra/tour360/$', paid_services.views.tour360, name='tour360'),
    url(r'^extra/legal_services/$', paid_services.views.legal_services, name='legal_services'),
    url(r'^extra/analysis-old/$', paid_services.views.analysis, name='analysis'),
    url(r'^extra/notary/$', paid_services.views.notary, name='notary'),
    url(r'^extra/interior3d/$', paid_services.views.interior3d, name='interior3d'),
    url(r'^extra/ocenka_nedvizh/$', paid_services.views.ocenka_nedvizh, name='ocenka_nedvizh'),
]
