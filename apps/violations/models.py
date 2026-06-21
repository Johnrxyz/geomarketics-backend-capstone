from django.db import models
from django.conf import settings

class Violation(models.Model):
    SEVERITY_LOW = 'low'
    SEVERITY_MEDIUM = 'medium'
    SEVERITY_HIGH = 'high'
    SEVERITY_CRITICAL = 'critical'
    SEVERITY_CHOICES = [
        (SEVERITY_LOW, 'Low'),
        (SEVERITY_MEDIUM, 'Medium'),
        (SEVERITY_HIGH, 'High'),
        (SEVERITY_CRITICAL, 'Critical'),
    ]

    STATUS_ACTIVE = 'active'
    STATUS_RESOLVED = 'resolved'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_RESOLVED, 'Resolved'),
    ]

    vendor = models.ForeignKey('vendors.Vendor', on_delete=models.CASCADE, related_name='violations')
    session = models.ForeignKey(
        'sanitation.SanitationSession', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='violations')
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='issued_violations')
    violation_date = models.DateField()
    violation_type = models.CharField(max_length=100)
    description = models.TextField()
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default=SEVERITY_MEDIUM)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-violation_date']

    def __str__(self):
        return f"{self.violation_type} - {self.vendor}"


class Penalty(models.Model):
    STATUS_UNPAID = 'unpaid'
    STATUS_PAID = 'paid'
    STATUS_WAIVED = 'waived'
    STATUS_CHOICES = [
        (STATUS_UNPAID, 'Unpaid'),
        (STATUS_PAID, 'Paid'),
        (STATUS_WAIVED, 'Waived'),
    ]

    violation = models.ForeignKey(Violation, on_delete=models.CASCADE, related_name='penalties')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    due_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_UNPAID)
    paid_date = models.DateField(null=True, blank=True)
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-due_date']

    def __str__(self):
        return f"Penalty for {self.violation}"
