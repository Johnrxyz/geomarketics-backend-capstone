from django.db import models
from django.conf import settings


# ── Commodity taxonomy ──────────────────────────────────────────────────────

class CommodityCategory(models.Model):
    """
    Top-level grouping of commodities as they appear in the DA price report.
    Order matches the page-order in FORMAT_B PDFs.
    """
    UNIT_KG    = 'kg'
    UNIT_LITER = 'liter'
    UNIT_PIECE = 'piece'
    UNIT_CHOICES = [
        (UNIT_KG,    'Kilogram (kg)'),
        (UNIT_LITER, 'Liter'),
        (UNIT_PIECE, 'Piece'),
    ]

    name         = models.CharField(max_length=100, unique=True)
    order        = models.PositiveSmallIntegerField(default=0)
    default_unit = models.CharField(
        max_length=20, choices=UNIT_CHOICES, default=UNIT_KG,
        help_text='Unit used for all commodities in this category unless overridden.',
    )

    class Meta:
        ordering = ['order']
        verbose_name_plural = 'Commodity Categories'

    def __str__(self):
        return self.name


class Commodity(models.Model):
    """
    Canonical commodity record. One row per (name, unit, category) triple.
    The category distinguishes e.g. "Basmati" under IMPORTED vs LOCAL rice.
    """
    UNIT_KG     = 'kg'
    UNIT_LITER  = 'liter'
    UNIT_PIECE  = 'piece'
    UNIT_DOZEN  = 'dozen'
    UNIT_PACK   = 'pack'
    UNIT_CAN    = 'can'
    UNIT_BUNDLE = 'bundle'
    UNIT_CHOICES = [
        (UNIT_KG,     'Kilogram (kg)'),
        (UNIT_LITER,  'Liter'),
        (UNIT_PIECE,  'Piece'),
        (UNIT_DOZEN,  'Dozen'),
        (UNIT_PACK,   'Pack'),
        (UNIT_CAN,    'Can'),
        (UNIT_BUNDLE, 'Bundle'),
    ]

    category       = models.ForeignKey(CommodityCategory, on_delete=models.CASCADE, related_name='commodities')
    name           = models.CharField(max_length=200)
    unit           = models.CharField(max_length=20, choices=UNIT_CHOICES, default=UNIT_KG)
    order          = models.PositiveSmallIntegerField(default=0)
    is_active      = models.BooleanField(default=True)

    class Meta:
        ordering = ['category__order', 'order']
        verbose_name_plural = 'Commodities'
        constraints = [
            # Changed from UNIQUE(name, unit) → UNIQUE(name, unit, category)
            # Reason: same commodity name (e.g. "Basmati") appears in both
            # IMPORTED COMMERCIAL RICE and LOCAL COMMERCIAL RICE categories.
            models.UniqueConstraint(
                fields=['name', 'unit', 'category'],
                name='uq_commodity_name_unit_category',
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.unit}) — {self.category.name}"


class CommodityAlias(models.Model):
    """
    Alternative names for a commodity as they may appear in source PDFs.
    Used by the normalization layer to resolve raw names to canonical records.
    """
    SOURCE_AUDIT = 'audit'
    SOURCE_ADMIN = 'admin'
    SOURCE_AUTO  = 'auto'
    SOURCE_CHOICES = [
        (SOURCE_AUDIT, 'Phase 0 Audit'),
        (SOURCE_ADMIN, 'Admin Review'),
        (SOURCE_AUTO,  'Automatic'),
    ]

    commodity  = models.ForeignKey(Commodity, on_delete=models.CASCADE, related_name='aliases')
    alias      = models.CharField(max_length=300, unique=True)
    source     = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_AUDIT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Commodity Aliases'
        indexes = [models.Index(fields=['alias'], name='idx_commodity_alias_lookup')]

    def __str__(self):
        return f'"{self.alias}" → {self.commodity.name}'


# ── Price Snapshots ─────────────────────────────────────────────────────────

class PriceSnapshot(models.Model):
    """
    Immutable daily price record.  One row per (market, commodity, survey_date, source_document).
    Never overwrite — always insert new rows.
    NULL means the price was not reported in the source. 0 is never used as a substitute.
    """
    QUALITY_VERIFIED    = 'verified'
    QUALITY_PROVISIONAL = 'provisional'
    DATA_QUALITY_CHOICES = [
        (QUALITY_VERIFIED,    'Verified — all fields parsed cleanly'),
        (QUALITY_PROVISIONAL, 'Provisional — partial data, some fields may be missing'),
    ]

    market            = models.ForeignKey('markets.Market',         on_delete=models.RESTRICT, related_name='price_snapshots')
    commodity         = models.ForeignKey(Commodity,                on_delete=models.RESTRICT, related_name='price_snapshots')
    source_document   = models.ForeignKey('ingestion.SourceDocument', on_delete=models.RESTRICT, related_name='price_snapshots')
    survey_date       = models.DateField(db_index=True)

    # FORMAT_B price fields — all nullable (NULL = not reported in source)
    price_min        = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    price_max        = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    average_price    = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    prevailing_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    data_quality = models.CharField(max_length=20, choices=DATA_QUALITY_CHOICES, default=QUALITY_VERIFIED)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-survey_date']
        constraints = [
            models.UniqueConstraint(
                fields=['market', 'commodity', 'survey_date', 'source_document'],
                name='uq_price_snapshot',
            )
        ]
        indexes = [
            models.Index(fields=['-survey_date'],             name='idx_snapshot_date'),
            models.Index(fields=['market', '-survey_date'],   name='idx_snapshot_market_date'),
            models.Index(fields=['commodity', '-survey_date'], name='idx_snapshot_commodity_date'),
        ]

    def __str__(self):
        return f'{self.survey_date} | {self.market} | {self.commodity}'



