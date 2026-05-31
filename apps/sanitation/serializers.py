from rest_framework import serializers
from .models import SanitationCheckItem, SanitationSession, SanitationRecord


class SanitationCheckItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SanitationCheckItem
        fields = ['id', 'name', 'label', 'order', 'is_active']


class SanitationRecordSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source='vendor.full_name', read_only=True)
    check_item_label = serializers.CharField(source='check_item.label', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = SanitationRecord
        fields = ['id', 'session', 'vendor', 'vendor_name', 'check_item',
                  'check_item_label', 'status', 'status_display', 'remarks']


class SanitationSessionSerializer(serializers.ModelSerializer):
    section_name = serializers.CharField(source='section.name', read_only=True)
    conducted_by_name = serializers.SerializerMethodField()
    records = SanitationRecordSerializer(many=True, read_only=True)
    total_vendors = serializers.SerializerMethodField()
    passed_count = serializers.SerializerMethodField()

    class Meta:
        model = SanitationSession
        fields = ['id', 'conducted_by', 'conducted_by_name', 'section', 'section_name',
                  'date', 'notes', 'compliance_rate', 'records',
                  'total_vendors', 'passed_count', 'created_at']
        read_only_fields = ['id', 'created_at', 'compliance_rate']

    def get_conducted_by_name(self, obj):
        if obj.conducted_by:
            return obj.conducted_by.get_full_name() or obj.conducted_by.username
        return None

    def get_total_vendors(self, obj):
        return obj.records.values('vendor').distinct().count()

    def get_passed_count(self, obj):
        return obj.records.filter(status='pass').values('vendor').distinct().count()


class SanitationSessionListSerializer(serializers.ModelSerializer):
    section_name = serializers.CharField(source='section.name', read_only=True)
    conducted_by_name = serializers.SerializerMethodField()

    class Meta:
        model = SanitationSession
        fields = ['id', 'conducted_by', 'conducted_by_name', 'section', 'section_name',
                  'date', 'compliance_rate', 'created_at']

    def get_conducted_by_name(self, obj):
        if obj.conducted_by:
            return obj.conducted_by.get_full_name() or obj.conducted_by.username
        return None
