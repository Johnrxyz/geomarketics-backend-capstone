from django.db import models
from django.conf import settings


class Complaint(models.Model):
    STATUS_OPEN = 'open'
    STATUS_REVIEWING = 'reviewing'
    STATUS_RESOLVED = 'resolved'
    STATUS_DISMISSED = 'dismissed'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Open'),
        (STATUS_REVIEWING, 'Under Review'),
        (STATUS_RESOLVED, 'Resolved'),
        (STATUS_DISMISSED, 'Dismissed'),
    ]

    CATEGORY_SANITATION = 'sanitation'
    CATEGORY_OVERPRICING = 'overpricing'
    CATEGORY_SAFETY = 'safety'
    CATEGORY_FOOD_SAFETY = 'food_safety'
    CATEGORY_PERMIT = 'permit'
    CATEGORY_DISPLAY = 'display'
    CATEGORY_NOISE = 'noise'
    CATEGORY_OTHER = 'other'
    CATEGORY_CHOICES = [
        (CATEGORY_SANITATION, 'Sanitation'),
        (CATEGORY_OVERPRICING, 'Overpricing'),
        (CATEGORY_SAFETY, 'Safety Hazard'),
        (CATEGORY_FOOD_SAFETY, 'Food Safety'),
        (CATEGORY_PERMIT, 'Permit Violation'),
        (CATEGORY_DISPLAY, 'Display Violation'),
        (CATEGORY_NOISE, 'Noise/Disturbance'),
        (CATEGORY_OTHER, 'Other'),
    ]

    complaint_number = models.CharField(max_length=20, unique=True, blank=True)
    complainant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='submitted_complaints',
    )
    complainant_name = models.CharField(max_length=200, blank=True)
    complainant_contact = models.CharField(max_length=100, blank=True)
    vendor = models.ForeignKey(
        'vendors.Vendor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='complaints',
    )
    stall = models.ForeignKey(
        'vendors.Stall',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='complaints',
    )
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default=CATEGORY_OTHER)
    subject = models.CharField(max_length=300)
    description = models.TextField()
    evidence_file = models.FileField(upload_to='complaints/', null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    resolution_notes = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_complaints',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.complaint_number} - {self.subject}"

    def save(self, *args, **kwargs):
        if not self.complaint_number:
            last = Complaint.objects.order_by('-id').first()
            num = (last.id + 1) if last else 1
            self.complaint_number = f"CMP-{num:03d}"
        super().save(*args, **kwargs)
