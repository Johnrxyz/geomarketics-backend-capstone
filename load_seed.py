import json
import os
import django
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings.dev')
django.setup()

from apps.prices.models import CommodityCategory, Commodity, CommodityAlias
from apps.markets.models import Market, MarketAlias

def load():
    base = r"D:\Ryzen 7 5700G\CAPSTONE - LC PUBLIC MARKET\bantay_presyo_audit\phases_audit\seed_data"
    
    # 1. Categories
    with open(os.path.join(base, 'commodity_categories.json'), 'r') as f:
        data = json.load(f)
        for item in data:
            f = item['fields']
            CommodityCategory.objects.update_or_create(
                pk=item['pk'],
                defaults=f
            )
            
    # 2. Commodities
    with open(os.path.join(base, 'commodities.json'), 'r') as f:
        data = json.load(f)
        for item in data:
            f = item['fields']
            f['category_id'] = f.pop('category')
            Commodity.objects.update_or_create(
                pk=item['pk'],
                defaults=f
            )
            
    # 3. Commodity Aliases
    with open(os.path.join(base, 'commodity_aliases.json'), 'r') as f:
        data = json.load(f)
        for item in data:
            f = item['fields']
            f['commodity_id'] = f.pop('commodity')
            f['created_at'] = timezone.now()
            CommodityAlias.objects.update_or_create(
                pk=item['pk'],
                defaults=f
            )
            
    # 4. Markets
    with open(os.path.join(base, 'markets.json'), 'r') as f:
        data = json.load(f)
        for item in data:
            f = item['fields']
            Market.objects.update_or_create(
                pk=item['pk'],
                defaults=f
            )
            
    # 5. Market Aliases
    with open(os.path.join(base, 'market_aliases.json'), 'r') as f:
        data = json.load(f)
        for item in data:
            f = item['fields']
            f['market_id'] = f.pop('market')
            f['created_at'] = timezone.now()
            MarketAlias.objects.update_or_create(
                pk=item['pk'],
                defaults=f
            )

    print("Seed data loaded successfully!")

if __name__ == '__main__':
    load()
