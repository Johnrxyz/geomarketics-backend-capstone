import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from apps.vendors.models import Vendor, Stall, MarketSection

User = get_user_model()
admin_user = User.objects.filter(role='admin').first()

# Make sure we have a vendor
vendor = Vendor.objects.first()

if admin_user and vendor:
    c = Client()
    c.force_login(admin_user)
    
    # 5MB dummy string to test Payload Too Large
    large_base64 = "data:image/jpeg;base64," + ("A" * 5000000)
    
    res = c.post('/api/violations/', {
        'vendor': vendor.id,
        'violation_type': 'Camera Test',
        'description': 'Testing camera upload size limit',
        'severity': 'low',
        'violation_date': '2026-06-23',
        'photo': large_base64
    })
    print("STATUS:", res.status_code)
    print("RESPONSE:", res.content[:200])
else:
    print("Missing admin or vendor")
