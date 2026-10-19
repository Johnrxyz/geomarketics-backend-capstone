from rest_framework import serializers
from django.urls import reverse
from .models import Complaint, Blotter
from apps.vendors.serializers import VendorSerializer, StallListSerializer
from apps.documents.services.upload_validation import validate_document_upload


class ComplaintEvidenceField(serializers.FileField):
    """Accept uploads while returning only the authenticated Django endpoint."""

    def get_attribute(self, instance):
        self._complaint_instance = instance
        return super().get_attribute(instance)

    def to_internal_value(self, data):
        upload = super().to_internal_value(data)
        validate_document_upload(upload, field_name='evidence_file')
        return upload

    def to_representation(self, value):
        if not value:
            return None
        complaint = getattr(self, '_complaint_instance', None)
        if complaint is None or not complaint.pk:
            return None
        url = reverse('complaint-evidence', kwargs={'pk': complaint.pk})
        request = self.context.get('request')
        return request.build_absolute_uri(url) if request else url


class ComplaintSerializer(serializers.ModelSerializer):
    evidence_file = ComplaintEvidenceField(required=False, allow_null=True)
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
                  'is_flagged_spam', 'spam_reason',
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


class ComplaintVendorSerializer(serializers.ModelSerializer):
    """
    Complaint serializer for vendor-role access.
    Omits all complainant identity fields (name, contact, FK) to preserve
    the complainant's privacy from the party they are complaining about.
    Vendors can see the complaint details but not WHO filed it.
    """
    vendor_name = serializers.SerializerMethodField()
    stall_number = serializers.SerializerMethodField()
    evidence_file = ComplaintEvidenceField(required=False, allow_null=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Complaint
        # Deliberately excludes: complainant, complainant_name, complainant_contact
        fields = ['id', 'complaint_number', 'vendor', 'vendor_name',
                  'stall', 'stall_number', 'category', 'category_display',
                  'subject', 'description', 'evidence_file', 'status', 'status_display',
                  'is_flagged_spam',
                  'resolution_notes', 'resolved_at', 'created_at', 'updated_at']
        read_only_fields = ['id', 'complaint_number', 'created_at', 'updated_at']

    def get_vendor_name(self, obj):
        return obj.vendor.full_name if obj.vendor else None

    def get_stall_number(self, obj):
        return obj.stall.stall_number if obj.stall else None



class ComplaintCreateSerializer(serializers.ModelSerializer):
    """Used for POST /complaints/ — write fields plus read-back of id/number."""
    evidence_file = ComplaintEvidenceField(required=False, allow_null=True)

    class Meta:
        model = Complaint
        fields = ['id', 'complaint_number', 'vendor', 'stall', 'category',
                  'subject', 'description', 'evidence_file',
                  'complainant_name', 'complainant_contact']
        read_only_fields = ['id', 'complaint_number']

    def create(self, validated_data):
        # Keep the uploaded asset recoverable if the database insert fails
        # after FileField.pre_save has written it to storage.
        complaint = Complaint(**validated_data)
        try:
            complaint.save()
        except Exception:
            evidence = complaint.evidence_file
            if evidence and evidence.name and getattr(evidence, '_committed', False):
                try:
                    evidence.storage.delete(evidence.name)
                except Exception:
                    # Storage adapters sanitize their own provider diagnostics.
                    pass
            raise
        return complaint


class BlotterSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source='vendor.full_name', read_only=True)
    recorded_by_name = serializers.CharField(source='recorded_by.get_full_name', read_only=True)

    class Meta:
        model = Blotter
        fields = '__all__'
