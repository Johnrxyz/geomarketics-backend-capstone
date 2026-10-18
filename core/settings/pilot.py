"""Production-safe settings for the supervised PythonAnywhere SQLite pilot.

Activate only after setting DJANGO_SETTINGS_MODULE=core.settings.pilot and
enabling PythonAnywhere's HTTPS redirect at the hosting edge. No proxy scheme
header is assumed here because the deployed WSGI forwarding behavior has not
been independently verified.
"""

import os

from .base import *  # noqa: F403
from ._pilot_validation import (
    parse_allowed_hosts,
    parse_cors_origins,
    required_env,
    validate_secret_key,
)


DEBUG = False
SECRET_KEY = validate_secret_key(required_env("SECRET_KEY", os.environ))
ALLOWED_HOSTS = parse_allowed_hosts(required_env("ALLOWED_HOSTS", os.environ))
CORS_ALLOWED_ORIGINS = parse_cors_origins(
    required_env("CORS_ALLOWED_ORIGINS", os.environ)
)
CORS_ALLOW_ALL_ORIGINS = False

# Keep the same on-disk database used by core.settings.dev. The in-memory test
# database prevents Django's test runner from writing to the pilot SQLite file.
PILOT_DATABASE_PATH = BASE_DIR / "db.sqlite3"  # noqa: F405
PILOT_TEST_DATABASE_NAME = ":memory:"
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": PILOT_DATABASE_PATH,
        "OPTIONS": {"timeout": 20},
        "TEST": {"NAME": PILOT_TEST_DATABASE_NAME},
    }
}

# The frontend origins allowed to call the API are also the exact trusted
# origins for Django's CSRF checks. HTTPS-only validation is performed above.
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS

# PythonAnywhere must enforce HTTPS before this settings module is activated.
# Keep Django's redirect and proxy-scheme inference disabled until the actual
# WSGI forwarding header is verified, avoiding redirect loops caused by an
# untrusted or absent X-Forwarded-Proto header.
SECURE_SSL_REDIRECT = False
SECURE_PROXY_SSL_HEADER = None
USE_X_FORWARDED_HOST = False
SECURE_HSTS_SECONDS = 0

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
