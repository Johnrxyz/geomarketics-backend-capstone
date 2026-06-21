from rest_framework import serializers
from .models import CommodityCategory, Commodity, PriceSnapshot


class CommodityCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = CommodityCategory
        fields = ['id', 'name', 'order']


class CommoditySerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    unit_display = serializers.CharField(source='get_unit_display', read_only=True)

    class Meta:
        model = Commodity
        fields = ['id', 'category', 'category_name', 'name', 'unit', 'unit_display',
                  'order', 'is_active']





class PriceSnapshotSerializer(serializers.ModelSerializer):
    market_name = serializers.CharField(source='market.name', read_only=True)
    commodity_name = serializers.CharField(source='commodity.name', read_only=True)
    commodity_unit = serializers.CharField(source='commodity.unit', read_only=True)
    category_name = serializers.CharField(source='commodity.category.name', read_only=True)

    class Meta:
        model = PriceSnapshot
        fields = [
            'id', 'market', 'market_name', 'commodity', 'commodity_name',
            'commodity_unit', 'category_name', 'source_document', 'survey_date',
            'price_min', 'price_max', 'average_price', 'prevailing_price',
            'data_quality', 'created_at'
        ]

