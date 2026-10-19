from pathlib import Path

from django.urls import reverse
from rest_framework import serializers

from .models import Document, DocumentPage, DocumentReview
from .services.upload_validation import validate_document_upload
from .storage import CLOUDINARY_PREFIX


class DocumentReviewSerializer(serializers.ModelSerializer):
    reviewed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = DocumentReview
        fields = ['status', 'notes', 'reviewed_by_name', 'reviewed_at']

    def get_reviewed_by_name(self, obj):
        return (obj.reviewed_by.get_full_name() or obj.reviewed_by.username) if obj.reviewed_by else None


class DocumentPageSerializer(serializers.ModelSerializer):
    file_name = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = DocumentPage
        fields = ['id', 'file_name', 'file_url', 'page_upload_order', 'detected_page_number']

    def get_file_name(self, obj):
        if obj.file and obj.file.name.startswith(CLOUDINARY_PREFIX):
            return f'Contract page {obj.page_upload_order}{Path(obj.file.name).suffix}'
        return Path(obj.file.name).name if obj.file else None

    def get_file_url(self, obj):
        request = self.context.get('request')
        url = reverse('document-page-file', kwargs={'pk': obj.document_id, 'page_id': obj.pk})
        return request.build_absolute_uri(url) if request else url


class DocumentSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source='vendor.full_name', read_only=True)
    stall_number = serializers.SerializerMethodField()
    document_type_display = serializers.CharField(source='get_document_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    reviewed_by_name = serializers.SerializerMethodField()
    file = serializers.FileField(write_only=True, required=False, allow_empty_file=False)
    file_name = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()
    pages = DocumentPageSerializer(many=True, read_only=True)
    review_history = DocumentReviewSerializer(many=True, read_only=True)

    class Meta:
        model = Document
        fields = ['id', 'vendor', 'vendor_name', 'stall_number', 'uploaded_by',
                  'reviewed_by', 'reviewed_by_name', 'document_type', 'document_type_display',
                  'title', 'file', 'file_name', 'file_url', 'pages', 'review_history',
                  'file_size', 'status', 'status_display', 'expiry_date', 'review_notes',
                  'reviewed_at', 'created_at', 'updated_at', 'validation_results', 'ocr_status',
                  'raw_ocr_text', 'extracted_data', 'detected_type', 'confidence_score',
                  'classification_metadata', 'replaces']
        read_only_fields = ['id', 'created_at', 'updated_at', 'reviewed_at', 'file_size',
                            'status', 'review_notes', 'validation_results', 'ocr_status',
                            'raw_ocr_text', 'extracted_data', 'detected_type', 'confidence_score',
                            'classification_metadata', 'vendor', 'uploaded_by', 'reviewed_by']

    def validate_file(self, upload):
        validate_document_upload(upload)
        return upload

    def validate_replaces(self, replaces):
        request = self.context.get('request')
        if replaces and (request is None or not hasattr(request.user, 'vendor_profile') or replaces.vendor_id != request.user.vendor_profile.pk):
            raise serializers.ValidationError('A document can only replace another document belonging to your vendor profile.')
        return replaces

    def validate(self, attrs):
        upload = attrs.get('file')
        if upload:
            attrs['file_size'] = f'{upload.size / (1024 * 1024):.2f} MB'
        return attrs

    def get_stall_number(self, obj):
        return obj.vendor.stall.stall_number if obj.vendor and obj.vendor.stall else None

    def get_reviewed_by_name(self, obj):
        if obj.reviewed_by:
            return obj.reviewed_by.get_full_name() or obj.reviewed_by.username
        return None

    def get_file_name(self, obj):
        if obj.file and obj.file.name.startswith(CLOUDINARY_PREFIX):
            return obj.title or f'{obj.get_document_type_display()}{Path(obj.file.name).suffix}'
        return Path(obj.file.name).name if obj.file else None

    def get_file_url(self, obj):
        if not obj.file:
            return None
        request = self.context.get('request')
        url = reverse('document-file', kwargs={'pk': obj.pk})
        return request.build_absolute_uri(url) if request else url
