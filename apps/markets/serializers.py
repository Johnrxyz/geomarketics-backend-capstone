from rest_framework import serializers
from .models import Market, MarketAlias, UnknownEntity

class MarketSerializer(serializers.ModelSerializer):
    class Meta:
        model = Market
        fields = '__all__'

class MarketAliasSerializer(serializers.ModelSerializer):
    market_name = serializers.CharField(source='market.name', read_only=True)

    class Meta:
        model = MarketAlias
        fields = '__all__'

class UnknownEntitySerializer(serializers.ModelSerializer):
    resolved_to_market_name = serializers.CharField(source='resolved_to_market.name', read_only=True)
    resolved_to_commodity_name = serializers.CharField(source='resolved_to_commodity.name', read_only=True)
    source_document_filename = serializers.CharField(source='source_document.file.name', read_only=True)

    class Meta:
        model = UnknownEntity
        fields = '__all__'
