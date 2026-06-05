from .base import *  # noqa
import os

DEBUG = False
ALLOWED_HOSTS = env('ALLOWED_HOSTS', 'localhost').split(',')

# PostgreSQL — required for production
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME':     env('DB_NAME',     'geomarketics'),
        'USER':     env('DB_USER',     'postgres'),
        'PASSWORD': env('DB_PASSWORD', ''),
        'HOST':     env('DB_HOST',     'localhost'),
        'PORT':     env('DB_PORT',     '5432'),
    }
}

CORS_ALLOWED_ORIGINS = env('CORS_ALLOWED_ORIGINS', 'http://localhost:3000').split(',')

# Security
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
