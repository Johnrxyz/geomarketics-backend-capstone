from django.core.management.base import BaseCommand
from apps.vendors.models import Vendor
from apps.analytics.services import compute_risk_for_vendor


class Command(BaseCommand):
    help = 'Recompute AI risk profiles for all active vendors'

    def handle(self, *args, **options):
        n = 0
        for v in Vendor.objects.filter(is_active=True):
            compute_risk_for_vendor(v)
            n += 1
        self.stdout.write(self.style.SUCCESS(f'Recomputed {n} risk profiles'))
