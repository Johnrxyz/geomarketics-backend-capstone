from django.db import models
from django.conf import settings


class Market(models.Model):
    """Canonical market record. One row per physical market."""

    MARKET_TYPE_PUBLIC = 'public'
    MARKET_TYPE_PRIVATE = 'private'
    MARKET_TYPE_MALL = 'mall'
    MARKET_TYPE_CHOICES = [
        (MARKET_TYPE_PUBLIC,  'Public Market'),
        (MARKET_TYPE_PRIVATE, 'Private Market'),
        (MARKET_TYPE_MALL,    'Mall / Commercial'),
    ]

    PROVINCE_CAVITE   = 'Cavite'
    PROVINCE_LAGUNA   = 'Laguna'
    PROVINCE_BATANGAS = 'Batangas'
    PROVINCE_RIZAL    = 'Rizal'
    PROVINCE_QUEZON   = 'Quezon'
    PROVINCE_CHOICES  = [
        (PROVINCE_CAVITE,   'Cavite'),
        (PROVINCE_LAGUNA,   'Laguna'),
        (PROVINCE_BATANGAS, 'Batangas'),
        (PROVINCE_RIZAL,    'Rizal'),
        (PROVINCE_QUEZON,   'Quezon'),
    ]

    name              = models.CharField(max_length=200, unique=True)
    province          = models.CharField(max_length=100, choices=PROVINCE_CHOICES, db_index=True)
    city_municipality = models.CharField(max_length=100, blank=True)
    address           = models.TextField(blank=True, null=True)
    market_type       = models.CharField(max_length=20, choices=MARKET_TYPE_CHOICES, default=MARKET_TYPE_PUBLIC)
    is_active         = models.BooleanField(default=True, db_index=True)
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['province', 'name']

    def __str__(self):
        return self.name


class MarketAlias(models.Model):
    """
    Alternative names that may appear in source PDFs or external references.
    The normalization layer resolves any alias to its canonical Market.
    """
    SOURCE_AUDIT = 'audit'
    SOURCE_ADMIN = 'admin'
    SOURCE_AUTO  = 'auto'
    SOURCE_CHOICES = [
        (SOURCE_AUDIT, 'Phase 0 Audit'),
        (SOURCE_ADMIN, 'Admin Review'),
        (SOURCE_AUTO,  'Automatic'),
    ]

    market = models.ForeignKey(Market, on_delete=models.CASCADE, related_name='aliases')
    alias  = models.CharField(max_length=300, unique=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_AUDIT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Market Aliases'
        indexes = [models.Index(fields=['alias'], name='idx_market_alias_lookup')]

    def __str__(self):
        return f'"{self.alias}" → {self.market.name}'


class UnknownEntity(models.Model):
    """
    Logged when the normalization layer cannot resolve a raw name from a PDF
    to any canonical Market or Commodity (including aliases).
    Reviewed and resolved by an admin before reprocessing the source document.
    """
    ENTITY_MARKET    = 'market'
    ENTITY_COMMODITY = 'commodity'
    ENTITY_TYPE_CHOICES = [
        (ENTITY_MARKET,    'Market'),
        (ENTITY_COMMODITY, 'Commodity'),
    ]

    STATUS_UNRESOLVED = 'unresolved'
    STATUS_RESOLVED   = 'resolved'
    STATUS_IGNORED    = 'ignored'
    STATUS_NEW_RECORD = 'new_record_created'
    STATUS_CHOICES = [
        (STATUS_UNRESOLVED, 'Unresolved'),
        (STATUS_RESOLVED,   'Resolved — mapped to existing record'),
        (STATUS_IGNORED,    'Ignored — not a real entity'),
        (STATUS_NEW_RECORD, 'New record created'),
    ]

    source_document       = models.ForeignKey(
        'ingestion.SourceDocument',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='unknown_entities',
    )
    entity_type           = models.CharField(max_length=20, choices=ENTITY_TYPE_CHOICES, db_index=True)
    raw_name              = models.TextField()
    resolved_to_market    = models.ForeignKey(
        Market,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='resolved_unknowns',
    )
    resolved_to_commodity = models.ForeignKey(
        'prices.Commodity',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='resolved_unknowns',
    )
    resolution_status = models.CharField(
        max_length=30, choices=STATUS_CHOICES, default=STATUS_UNRESOLVED, db_index=True
    )
    first_seen       = models.DateTimeField(auto_now_add=True)
    last_seen        = models.DateTimeField(auto_now=True)
    occurrence_count = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['entity_type', 'raw_name'],
                name='uq_unknown_entity_type_name',
            )
        ]
        ordering = ['-last_seen']
        verbose_name_plural = 'Unknown Entities'

    def __str__(self):
        return f'[{self.entity_type}] "{self.raw_name}" ({self.resolution_status})'


class Announcement(models.Model):
    CATEGORY_SCHEDULE = 'schedule'
    CATEGORY_HOLIDAY = 'holiday'
    CATEGORY_INSPECTION = 'inspection'
    CATEGORY_ADVISORY = 'advisory'
    CATEGORY_GENERAL = 'general'
    CATEGORY_CHOICES = [
        (CATEGORY_SCHEDULE, 'Schedule Change'),
        (CATEGORY_HOLIDAY, 'Holiday Closure'),
        (CATEGORY_INSPECTION, 'Inspection Date'),
        (CATEGORY_ADVISORY, 'Public Advisory'),
        (CATEGORY_GENERAL, 'General'),
    ]

    PRIORITY_LOW = 'low'
    PRIORITY_MEDIUM = 'medium'
    PRIORITY_HIGH = 'high'
    PRIORITY_CHOICES = [
        (PRIORITY_LOW, 'Low'),
        (PRIORITY_MEDIUM, 'Medium'),
        (PRIORITY_HIGH, 'High'),
    ]

    title = models.CharField(max_length=255)
    content = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=CATEGORY_GENERAL)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM)
    is_active = models.BooleanField(default=True)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.get_category_display()})"

