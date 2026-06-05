from django.core.management.base import BaseCommand
from django.db import models
from django.db.models import Count
from apps.ingestion.models import SourceDocument
from apps.prices.models import PriceSnapshot, Commodity, CommodityCategory
from apps.markets.models import Market

class Command(BaseCommand):
    help = "Run Data QA Verification Suite for ingested PriceSnapshots"

    def handle(self, *args, **options):
        self.stdout.write("Starting QA Verification Suite...\n")
        
        errors = 0
        
        # 1. Compare snapshot count per PDF
        self.stdout.write("--- 1. Snapshot Count per PDF ---")
        docs = SourceDocument.objects.filter(status=SourceDocument.STATUS_PROCESSED)
        for doc in docs:
            count = PriceSnapshot.objects.filter(source_document=doc).count()
            self.stdout.write(f"{doc.source_filename}: {count} snapshots")
            if count == 0:
                self.stderr.write(f"ERROR: No snapshots found for {doc.source_filename}")
                errors += 1

        # 2. Verify exactly 10 markets are represented
        self.stdout.write("\n--- 2. Market Representation ---")
        markets_with_data = PriceSnapshot.objects.values_list('market', flat=True).distinct().count()
        self.stdout.write(f"Markets with snapshots: {markets_with_data} / 10 expected")
        if markets_with_data != 10:
            self.stderr.write("ERROR: Not all 10 markets are represented!")
            errors += 1
            
        # 3. Verify exactly 13 categories are represented
        self.stdout.write("\n--- 3. Category Representation ---")
        cats_with_data = PriceSnapshot.objects.values_list('commodity__category', flat=True).distinct().count()
        self.stdout.write(f"Categories with snapshots: {cats_with_data} / 13 expected")
        if cats_with_data != 13:
            self.stderr.write("ERROR: Not all 13 categories are represented!")
            errors += 1

        # 4. Verify no duplicate snapshots exist
        self.stdout.write("\n--- 4. Duplicate Snapshots ---")
        duplicates = PriceSnapshot.objects.values(
            'market', 'commodity', 'survey_date', 'source_document'
        ).annotate(count=Count('id')).filter(count__gt=1)
        if duplicates.exists():
            self.stderr.write(f"ERROR: Found {duplicates.count()} duplicate snapshots!")
            for d in duplicates:
                self.stderr.write(f"  Duplicate: {d}")
            errors += 1
        else:
            self.stdout.write("OK: No duplicate snapshots found.")

        # 5. Verify no negative prices exist
        self.stdout.write("\n--- 5. Negative Prices ---")
        negatives = PriceSnapshot.objects.filter(
            models.Q(price_min__lt=0) |
            models.Q(price_max__lt=0) |
            models.Q(average_price__lt=0) |
            models.Q(prevailing_price__lt=0)
        )
        if negatives.exists():
            self.stderr.write(f"ERROR: Found {negatives.count()} snapshots with negative prices!")
            errors += 1
        else:
            self.stdout.write("OK: No negative prices found.")

        # 6. Verify price_min <= price_max
        self.stdout.write("\n--- 6. Min/Max Validation ---")
        invalid_minmax = PriceSnapshot.objects.filter(
            price_min__isnull=False, 
            price_max__isnull=False,
            price_min__gt=models.F('price_max')
        )
        if invalid_minmax.exists():
            self.stderr.write(f"ERROR: Found {invalid_minmax.count()} snapshots where min > max!")
            errors += 1
        else:
            self.stdout.write("OK: All min <= max checks passed.")

        # 7. Verify all SourceDocuments processed correctly
        self.stdout.write("\n--- 7. SourceDocument Status ---")
        failed = SourceDocument.objects.filter(status=SourceDocument.STATUS_FAILED).count()
        if failed > 0:
            self.stderr.write(f"ERROR: {failed} documents failed processing!")
            errors += 1
        else:
            self.stdout.write("OK: No failed documents.")

        self.stdout.write("\n==================================")
        if errors > 0:
            self.stderr.write(self.style.ERROR(f"QA Failed with {errors} error(s)."))
        else:
            self.stdout.write(self.style.SUCCESS("All QA Checks Passed!"))
