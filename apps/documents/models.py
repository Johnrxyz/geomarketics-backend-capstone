from django.db import models
from django.conf import settings


class Document(models.Model):
    TYPE_BUSINESS_PERMIT = 'business_permit'
    TYPE_SANITATION_CERT = 'sanitation_cert'
    TYPE_HEALTH_CERT = 'health_cert'
    TYPE_RENT_RECEIPT = 'rent_receipt'
    TYPE_TAX_CLEARANCE = 'tax_clearance'
    TYPE_CONTRACT = 'contract'
    TYPE_OTHER = 'other'
    TYPE_CHOICES = [
        (TYPE_BUSINESS_PERMIT, 'Business Permit'),
        (TYPE_SANITATION_CERT, 'Sanitation Certificate'),
        (TYPE_HEALTH_CERT, 'Health Certificate'),
        (TYPE_RENT_RECEIPT, 'Rent Receipt'),
        (TYPE_TAX_CLEARANCE, 'Tax Clearance'),
        (TYPE_CONTRACT, 'Contract'),
        (TYPE_OTHER, 'Other'),
    ]

    STATUS_INCOMPLETE = 'incomplete'
    STATUS_COMPLETE = 'complete'
    STATUS_PROCESSING = 'processing'
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_EXPIRED = 'expired'
    STATUS_RESUBMISSION = 'resubmission_required'
    STATUS_CHOICES = [
        (STATUS_INCOMPLETE, 'Incomplete'),
        (STATUS_COMPLETE, 'Complete'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_PENDING, 'Pending Review'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_EXPIRED, 'Expired'),
        (STATUS_RESUBMISSION, 'Resubmission Required'),
    ]

    vendor = models.ForeignKey(
        'vendors.Vendor',
        on_delete=models.CASCADE,
        related_name='documents',
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_documents',
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_documents',
    )
    document_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    title = models.CharField(max_length=200)
    file = models.FileField(upload_to='documents/', null=True, blank=True)
    file_size = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_INCOMPLETE)
    expiry_date = models.DateField(null=True, blank=True)
    
    # Document Verification & OCR
    validation_results = models.JSONField(null=True, blank=True)
    ocr_status = models.CharField(max_length=20, default='pending')
    raw_ocr_text = models.TextField(blank=True)
    extracted_data = models.JSONField(null=True, blank=True)
    detected_type = models.CharField(max_length=50, blank=True)
    confidence_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    classification_metadata = models.JSONField(null=True, blank=True)
    replaces = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='replaced_by')

    review_notes = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.vendor} - {self.get_document_type_display()}"


class DocumentPage(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='pages')
    file = models.FileField(upload_to='documents/pages/')
    raw_ocr_text = models.TextField(blank=True)
    page_upload_order = models.IntegerField()
    detected_page_number = models.IntegerField(null=True, blank=True)
    page_detection_confidence = models.FloatField(null=True, blank=True)
    image_quality_score = models.FloatField(null=True, blank=True)
    validation_results = models.JSONField(null=True, blank=True)
    warnings = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['page_upload_order']

    def __str__(self):
        return f"Page {self.detected_page_number} of {self.document}"


class ComplianceSignal(models.Model):
    SOURCE_SYSTEM = 'SYSTEM'
    SOURCE_OCR = 'OCR'
    SOURCE_ADMIN = 'ADMIN'
    SOURCE_VALIDATION = 'VALIDATION'
    SOURCE_CHOICES = [
        (SOURCE_SYSTEM, 'System'),
        (SOURCE_OCR, 'OCR Engine'),
        (SOURCE_ADMIN, 'Administrator'),
        (SOURCE_VALIDATION, 'Validation Checks'),
    ]

    vendor = models.ForeignKey('vendors.Vendor', on_delete=models.CASCADE, related_name='compliance_signals')
    document = models.ForeignKey(Document, on_delete=models.CASCADE, null=True, blank=True, related_name='compliance_signals')
    signal_type = models.CharField(max_length=50)
    description = models.TextField()
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_SYSTEM)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.source}] {self.signal_type} for {self.vendor}"
