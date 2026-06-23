from django.contrib import admin
from django.apps import apps

try:
    app_config = apps.get_app_config(__package__.split('.')[-1])
    for model in app_config.get_models():
        try:
            admin.site.register(model)
        except admin.sites.AlreadyRegistered:
            pass
except Exception:
    pass
