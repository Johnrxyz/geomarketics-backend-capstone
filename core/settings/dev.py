from .base import *  # noqa

DEBUG = True
ALLOWED_HOSTS = env('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# SQLite — fast local dev, no PostgreSQL install required
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        'OPTIONS': {
            'timeout': 20,
        }
    }
}

CORS_ALLOWED_ORIGINS = env('CORS_ALLOWED_ORIGINS', 'http://localhost:3000').split(',')
