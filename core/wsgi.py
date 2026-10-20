"""
WSGI config for core project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application
from core.cloudinary_bootstrap import initialize_cloudinary_proxy

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
initialize_cloudinary_proxy()

application = get_wsgi_application()
