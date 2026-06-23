import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from apps.prices.models import PriceSnapshot
from django.db.models import Count

counts = PriceSnapshot.objects.values('survey_date').annotate(count=Count('id')).order_by('-survey_date')[:5]
for c in counts:
    print(c)
