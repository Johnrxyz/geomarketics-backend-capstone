from rest_framework import serializers
from .models import Document, DocumentPage

class DocumentPageSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentPage
        fields = ['id', 'file', 'page_upload_order', 'detected_page_number']

class DocumentSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source='vendor.full_name', read_only=True)
    stall_number = serializers.SerializerMethodField()
    document_type_display = serializers.CharField(source='get_document_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    reviewed_by_name = serializers.SerializerMethodField()
    pages = DocumentPageSerializer(many=True, read_only=True)

    class Meta:
        model = Document
        fields = ['id', 'vendor', 'vendor_name', 'stall_number', 'uploaded_by',
                  'reviewed_by', 'reviewed_by_name', 'document_type', 'document_type_display',
                  'title', 'file', 'pages', 'file_size', 'status', 'status_display',
                  'expiry_date', 'review_notes', 'reviewed_at', 'created_at', 'updated_at',
                  'validation_results', 'ocr_status', 'raw_ocr_text', 'extracted_data',
                  'detected_type', 'confidence_score', 'classification_metadata', 'replaces']
        read_only_fields = ['id', 'created_at', 'updated_at', 'reviewed_at', 
                            'validation_results', 'ocr_status', 'raw_ocr_text', 
                            'extracted_data', 'detected_type', 'confidence_score',
                            'classification_metadata', 'vendor', 'uploaded_by', 'reviewed_by']

    def get_stall_number(self, obj):
        if obj.vendor and obj.vendor.stall:
            return obj.vendor.stall.stall_number
        return None

    def get_reviewed_by_name(self, obj):
        if obj.reviewed_by:
            return obj.reviewed_by.get_full_name() or obj.reviewed_by.username
        return None


class DocumentReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ['status', 'review_notes']
