from django.db import models
from django.conf import settings


class SanitationCheckItem(models.Model):
    name = models.CharField(max_length=100)
    label = models.CharField(max_length=100)
    order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.label


class SanitationSession(models.Model):
    conducted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sanitation_sessions',
    )
    section = models.ForeignKey(
        'vendors.MarketSection',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sanitation_sessions',
    )
    date = models.DateField()
    notes = models.TextField(blank=True)
    compliance_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"Sanitation Session {self.date} - {self.section}"

    def calculate_compliance(self):
        records = self.records.all()
        if not records.exists():
            return 0
        passed = records.filter(status='pass').count()
        return round((passed / records.count()) * 100, 2)


class SanitationRecord(models.Model):
    STATUS_PASS = 'pass'
    STATUS_FAIL = 'fail'
    STATUS_NA = 'na'
    STATUS_CHOICES = [
        (STATUS_PASS, 'Pass / Compliant'),
        (STATUS_FAIL, 'Fail / Non-Compliant'),
        (STATUS_NA, 'Not Applicable'),
    ]

    session = models.ForeignKey(SanitationSession, on_delete=models.CASCADE, related_name='records')
    vendor = models.ForeignKey(
        'vendors.Vendor',
        on_delete=models.CASCADE,
        related_name='sanitation_records',
    )
    check_item = models.ForeignKey(SanitationCheckItem, on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_NA)
    remarks = models.TextField(blank=True)

    class Meta:
        unique_together = ['session', 'vendor', 'check_item']
        ordering = ['vendor', 'check_item__order']

    def __str__(self):
        return f"{self.session} | {self.vendor} | {self.check_item}"
