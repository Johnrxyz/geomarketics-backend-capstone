import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings.dev')
django.setup()

from apps.markets.models import Market, MarketAlias

def fix_aliases():
    try:
        binan = Market.objects.get(name="Biñan City Public Market")
        MarketAlias.objects.get_or_create(
            market=binan,
            alias="Bi\ufffdan City Public Market",
            defaults={'source': 'auto'}
        )
        print("Added alias for Biñan City Public Market")
    except Market.DoesNotExist:
        print("Market not found!")

if __name__ == '__main__':
    fix_aliases()
