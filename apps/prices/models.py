from django.db import models
from django.conf import settings


class CommodityCategory(models.Model):
    name = models.CharField(max_length=100)
    roman_numeral = models.CharField(max_length=10, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order']
        verbose_name_plural = 'Commodity Categories'

    def __str__(self):
        return self.name


class Commodity(models.Model):
    UNIT_KG = 'kg'
    UNIT_LITER = 'liter'
    UNIT_PIECE = 'piece'
    UNIT_DOZEN = 'dozen'
    UNIT_PACK = 'pack'
    UNIT_CAN = 'can'
    UNIT_BUNDLE = 'bundle'
    UNIT_CHOICES = [
        (UNIT_KG, 'Kilogram (kg)'),
        (UNIT_LITER, 'Liter'),
        (UNIT_PIECE, 'Piece'),
        (UNIT_DOZEN, 'Dozen'),
        (UNIT_PACK, 'Pack'),
        (UNIT_CAN, 'Can'),
        (UNIT_BUNDLE, 'Bundle'),
    ]

    category = models.ForeignKey(CommodityCategory, on_delete=models.CASCADE, related_name='commodities')
    name = models.CharField(max_length=200)
    unit = models.CharField(max_length=20, choices=UNIT_CHOICES, default=UNIT_KG)
    standard_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['category__order', 'order']
        verbose_name_plural = 'Commodities'

    def __str__(self):
        return f"{self.name} ({self.unit})"


class PriceReport(models.Model):
    REMARK_HIGH = 'high'
    REMARK_LOW = 'low'
    REMARK_STABLE = 'stable'
    REMARK_UNAVAILABLE = 'unavailable'
    REMARK_SEASONAL = 'seasonal'

    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='price_reports',
    )
    report_date = models.DateField()
    period_label = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-report_date']

    def __str__(self):
        return f"Price Report {self.report_date}"


class PriceEntry(models.Model):
    REMARK_CHOICES = [
        ('high', 'High'),
        ('low', 'Low'),
        ('stable', 'Stable'),
        ('unavailable', 'Unavailable'),
        ('seasonal', 'Seasonal'),
    ]

    report = models.ForeignKey(PriceReport, on_delete=models.CASCADE, related_name='entries')
    commodity = models.ForeignKey(Commodity, on_delete=models.CASCADE, related_name='price_entries')
    respondent_1 = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    respondent_2 = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    respondent_3 = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    respondent_4 = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    respondent_5 = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    average_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    previous_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    remark = models.CharField(max_length=20, choices=REMARK_CHOICES, default='stable')

    class Meta:
        unique_together = ['report', 'commodity']

    def save(self, *args, **kwargs):
        prices = [
            self.respondent_1, self.respondent_2, self.respondent_3,
            self.respondent_4, self.respondent_5
        ]
        valid = [p for p in prices if p is not None]
        if valid:
            self.average_price = sum(valid) / len(valid)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.report} | {self.commodity}"
