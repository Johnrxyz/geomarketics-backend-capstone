import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from apps.ingestion.models import SourceDocument
from apps.prices.models import PriceSnapshot

print(f"SourceDocuments in DB: {SourceDocument.objects.count()}")
print(f"PriceSnapshots in DB: {PriceSnapshot.objects.count()}")
