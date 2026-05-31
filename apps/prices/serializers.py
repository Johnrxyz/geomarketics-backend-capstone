from rest_framework import serializers
from .models import CommodityCategory, Commodity, PriceReport, PriceEntry


class CommodityCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = CommodityCategory
        fields = ['id', 'name', 'roman_numeral', 'order']


class CommoditySerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    unit_display = serializers.CharField(source='get_unit_display', read_only=True)

    class Meta:
        model = Commodity
        fields = ['id', 'category', 'category_name', 'name', 'unit', 'unit_display',
                  'standard_price', 'order', 'is_active']


class PriceEntrySerializer(serializers.ModelSerializer):
    commodity_name = serializers.CharField(source='commodity.name', read_only=True)
    commodity_unit = serializers.CharField(source='commodity.unit', read_only=True)
    category_name = serializers.CharField(source='commodity.category.name', read_only=True)

    class Meta:
        model = PriceEntry
        fields = ['id', 'commodity', 'commodity_name', 'commodity_unit', 'category_name',
                  'respondent_1', 'respondent_2', 'respondent_3', 'respondent_4', 'respondent_5',
                  'average_price', 'previous_price', 'remark']


class PriceReportSerializer(serializers.ModelSerializer):
    entries = PriceEntrySerializer(many=True, read_only=True)
    submitted_by_name = serializers.SerializerMethodField()

    class Meta:
        model = PriceReport
        fields = ['id', 'submitted_by', 'submitted_by_name', 'report_date',
                  'period_label', 'notes', 'is_published', 'entries', 'created_at']
        read_only_fields = ['id', 'created_at']

    def get_submitted_by_name(self, obj):
        if obj.submitted_by:
            return obj.submitted_by.get_full_name() or obj.submitted_by.username
        return None


class PriceReportListSerializer(serializers.ModelSerializer):
    submitted_by_name = serializers.SerializerMethodField()
    entry_count = serializers.SerializerMethodField()

    class Meta:
        model = PriceReport
        fields = ['id', 'submitted_by', 'submitted_by_name', 'report_date',
                  'period_label', 'is_published', 'entry_count', 'created_at']

    def get_submitted_by_name(self, obj):
        if obj.submitted_by:
            return obj.submitted_by.get_full_name() or obj.submitted_by.username
        return None

    def get_entry_count(self, obj):
        return obj.entries.count()
