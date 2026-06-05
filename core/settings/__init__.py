# Re-export dev settings as default so all existing tooling still works.
# Switch to prod.py in production by setting:
#   DJANGO_SETTINGS_MODULE=core.settings.prod
from .dev import *  # noqa
