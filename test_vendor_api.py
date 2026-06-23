import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model

User = get_user_model()
vendor_user = User.objects.filter(role='vendor').first()
if vendor_user:
    c = Client()
    c.force_login(vendor_user)
    res = c.get('/api/violations/')
    print("STATUS:", res.status_code)
    if res.status_code == 500:
        import traceback
        try:
            from django.core.handlers.wsgi import WSGIRequest
            # we need to simulate the request to get the exact exception
            res = c.get('/api/violations/')
        except Exception as e:
            traceback.print_exc()
else:
    print("No vendor user found")
