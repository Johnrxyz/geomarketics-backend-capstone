from django.db import models
from django.conf import settings


class Document(models.Model):
    TYPE_BUSINESS_PERMIT = 'business_permit'
    TYPE_SANITATION_CERT = 'sanitation_cert'
    TYPE_HEALTH_CERT = 'health_cert'
    TYPE_RENT_RECEIPT = 'rent_receipt'
    TYPE_TAX_CLEARANCE = 'tax_clearance'
    TYPE_OTHER = 'other'
    TYPE_CHOICES = [
        (TYPE_BUSINESS_PERMIT, 'Business Permit'),
        (TYPE_SANITATION_CERT, 'Sanitation Certificate'),
        (TYPE_HEALTH_CERT, 'Health Certificate'),
        (TYPE_RENT_RECEIPT, 'Rent Receipt'),
        (TYPE_TAX_CLEARANCE, 'Tax Clearance'),
        (TYPE_OTHER, 'Other'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_EXPIRED = 'expired'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending Review'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_EXPIRED, 'Expired'),
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
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    expiry_date = models.DateField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.vendor} - {self.get_document_type_display()}"
