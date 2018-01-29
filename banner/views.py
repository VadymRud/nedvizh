from django.db.models import F
from django.shortcuts import redirect
from banner.models import Banner, BannerClick
import datetime

def banner_link_click(request, id):
    banner = Banner.objects.get(pk=id)

    clicks_updated_rows = BannerClick.objects.filter(banner=banner, date=datetime.date.today()).update(clicks=F('clicks')+1)
    if not clicks_updated_rows:
        BannerClick.objects.create(banner=banner, date=datetime.date.today(), clicks=1)

    return redirect(banner.url)