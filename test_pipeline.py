import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()
from apps.ingestion.models import SourceDocument
from apps.ingestion.pipeline.parser_format_b import parse_format_b

doc = SourceDocument.objects.get(id=1)
try:
    res = parse_format_b(doc)
    print("Parsed records count:", len(res))
    if len(res) > 0:
        print("First record:", res[0])
except Exception as e:
    import traceback
    traceback.print_exc()
