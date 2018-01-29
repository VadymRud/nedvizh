# coding: utf-8

def make_gtm_data(request, extra_data=None):
    if request.user.is_authenticated():
        gtm_data = {'clientId': str(request.user.uuid), 'dimension1': request.user.id}
    else:
        gtm_data = {}
    if extra_data:
        gtm_data.update(extra_data)
    return [gtm_data]

