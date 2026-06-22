from django.db import models
from django.conf import settings


class MarketSection(models.Model):
    code = models.CharField(max_length=10, unique=True)  # A, B, C, D, E
    name = models.CharField(max_length=100)               # Vegetables, Meat, Fish
    description = models.TextField(blank=True)
    color = models.CharField(max_length=20, default='#gray')

    class Meta:
        ordering = ['code']
        indexes = [
            models.Index(fields=['code'], name='idx_section_code'),
        ]

    def __str__(self):
        return f"Section {self.code} - {self.name}"


class Stall(models.Model):
    STATUS_OWNER = 'owner'
    STATUS_RENTED = 'rented'
    STATUS_STORAGE = 'storage'
    STATUS_SURRENDERED_BOLANTE = 'surrendered_bolante'
    STATUS_VACANT = 'vacant'
    STATUS_CLOSED = 'closed'
    STATUS_CHOICES = [
        (STATUS_OWNER, 'Managed by the Owner'),
        (STATUS_RENTED, 'With Renter'),
        (STATUS_STORAGE, 'Bodega'),
        (STATUS_SURRENDERED_BOLANTE, 'Surrendered w/ Bolante'),
        (STATUS_VACANT, 'Surrendered / Vacant'),
        (STATUS_CLOSED, 'Closed / No Operation'),
    ]

    stall_number = models.CharField(max_length=20, unique=True)
    section = models.ForeignKey(MarketSection, on_delete=models.PROTECT, related_name='stalls')
    category = models.CharField(max_length=100)
    area_sqm = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    monthly_rent = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_VACANT)
    BUILDING_CHOICES = [('main', 'Main Building'), ('annex', 'Annex Building')]
    FLOOR_CHOICES = [('1', '1st Floor'), ('2', '2nd Floor')]

    building = models.CharField(max_length=10, choices=BUILDING_CHOICES, default='main')
    floor = models.CharField(max_length=2, choices=FLOOR_CHOICES, default='1')
    svg_cell_id = models.CharField(max_length=100, blank=True, help_text='draw.io data-cell-id from the SVG floor plan')
    map_x = models.IntegerField(null=True, blank=True)
    map_y = models.IntegerField(null=True, blank=True)
    map_width = models.IntegerField(null=True, blank=True)
    map_height = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['stall_number']
        indexes = [
            models.Index(fields=['section', 'status'], name='idx_stall_section_status'),
        ]

    def __str__(self):
        return self.stall_number


class Vendor(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='vendor_profile',
        null=True,
        blank=True,
    )
    stall = models.OneToOneField(Stall, on_delete=models.SET_NULL, null=True, blank=True, related_name='vendor')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    products = models.TextField(blank=True, help_text='Comma-separated list of products sold')
    permit_number = models.CharField(max_length=50, blank=True)
    permit_expiry = models.DateField(null=True, blank=True)
    health_cert_expiry = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    compliance_rate = models.DecimalField(max_digits=5, decimal_places=2, default=100.00)
    joined_at = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def products_list(self):
        if self.products:
            return [p.strip() for p in self.products.split(',')]
        return []
