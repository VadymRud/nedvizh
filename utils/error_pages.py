from django_jinja import views

class PageNotFound(views.PageNotFound):
    tmpl_name = "404.jinja.html"

class PermissionDenied(views.PermissionDenied):
    tmpl_name = "403.jinja.html"

class ServerError(views.ServerError):
    tmpl_name = "500.jinja.html"