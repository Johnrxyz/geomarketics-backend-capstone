import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from apps.ingestion.models import SourceDocument
from apps.prices.models import PriceSnapshot

print("Unique SourceDocument publication dates:")
dates = SourceDocument.objects.values_list('publication_date', flat=True).distinct().order_by('publication_date')
for d in dates:
    print(" ", d)

print("\nUnique PriceSnapshot survey dates:")
snap_dates = PriceSnapshot.objects.values_list('survey_date', flat=True).distinct().order_by('survey_date')
for d in snap_dates:
    print(" ", d)
