from rest_framework import serializers
from .models import Complaint
from apps.vendors.serializers import VendorSerializer, StallListSerializer


class ComplaintSerializer(serializers.ModelSerializer):
    vendor_name = serializers.SerializerMethodField()
    stall_number = serializers.SerializerMethodField()
    complainant_display = serializers.SerializerMethodField()
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Complaint
        fields = ['id', 'complaint_number', 'complainant', 'complainant_name',
                  'complainant_contact', 'complainant_display', 'vendor', 'vendor_name',
                  'stall', 'stall_number', 'category', 'category_display',
                  'subject', 'description', 'evidence_file', 'status', 'status_display',
                  'resolution_notes', 'resolved_at', 'resolved_by', 'created_at', 'updated_at']
        read_only_fields = ['id', 'complaint_number', 'created_at', 'updated_at']

    def get_vendor_name(self, obj):
        return obj.vendor.full_name if obj.vendor else obj.complainant_name

    def get_stall_number(self, obj):
        return obj.stall.stall_number if obj.stall else None

    def get_complainant_display(self, obj):
        if obj.complainant:
            return obj.complainant.get_full_name() or obj.complainant.username
        return obj.complainant_name or 'Anonymous'


class ComplaintCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Complaint
        fields = ['vendor', 'stall', 'category', 'subject', 'description',
                  'evidence_file', 'complainant_name', 'complainant_contact']
