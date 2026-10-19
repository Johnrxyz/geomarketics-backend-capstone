from rest_framework import serializers
from .models import MarketSection, Stall, Vendor


class MarketSectionSerializer(serializers.ModelSerializer):
    stall_count = serializers.SerializerMethodField()
    occupied_count = serializers.SerializerMethodField()

    class Meta:
        model = MarketSection
        fields = ['id', 'code', 'name', 'description', 'color', 'stall_count', 'occupied_count']

    def get_stall_count(self, obj):
        return obj.stalls.count()

    def get_occupied_count(self, obj):
        return obj.stalls.filter(status='occupied').count()


class StallListSerializer(serializers.ModelSerializer):
    section_name = serializers.CharField(source='section.name', read_only=True)
    section_code = serializers.CharField(source='section.code', read_only=True)
    vendor_name = serializers.SerializerMethodField()
    # Expose map_x/map_y under the names the frontend expects (svg_x / svg_y)
    svg_x = serializers.IntegerField(source='map_x', read_only=True, allow_null=True)
    svg_y = serializers.IntegerField(source='map_y', read_only=True, allow_null=True)
    # Computed occupancy/compliance status fields for the map legend layer
    occupancy_status = serializers.SerializerMethodField()
    compliance_status = serializers.SerializerMethodField()

    class Meta:
        model = Stall
        fields = [
            'id', 'stall_number', 'section', 'section_name', 'section_code',
            'category', 'status', 'area_sqm', 'monthly_rent', 'vendor_name',
            'building', 'floor', 'svg_cell_id',
            # Coordinate fields in frontend-expected names (svg_x/svg_y) backed by map_x/map_y
            'svg_x', 'svg_y', 'map_width', 'map_height',
            # Computed status fields for map legend layer
            'occupancy_status', 'compliance_status',
        ]

    def get_vendor_name(self, obj):
        if hasattr(obj, 'vendor') and obj.vendor:
            return obj.vendor.full_name
        return None

    def get_occupancy_status(self, obj):
        """Return a normalised occupancy status for the map legend layer."""
        STATUS_MAP = {
            'owner': 'occupied',
            'rented': 'occupied',
            'storage': 'storage',
            'surrendered_bolante': 'surrendered',
            'vacant': 'vacant',
            'closed': 'closed',
        }
        return STATUS_MAP.get(obj.status, 'vacant')

    def get_compliance_status(self, obj):
        return None  # Populated by alert-summary overlay; not computed on list



class StallDetailSerializer(serializers.ModelSerializer):
    section_name = serializers.CharField(source='section.name', read_only=True)
    section_code = serializers.CharField(source='section.code', read_only=True)
    vendor = serializers.SerializerMethodField()

    class Meta:
        model = Stall
        fields = '__all__'

    def get_vendor(self, obj):
        if hasattr(obj, 'vendor') and obj.vendor:
            return VendorSerializer(obj.vendor).data
        return None


class StallPublicDetailSerializer(serializers.ModelSerializer):
    """Explicit public allowlist for anonymous and non-admin stall details."""
    section_name = serializers.CharField(source='section.name', read_only=True)
    section_code = serializers.CharField(source='section.code', read_only=True)
    vendor_name = serializers.SerializerMethodField()
    vendor = serializers.SerializerMethodField()
    svg_x = serializers.IntegerField(source='map_x', read_only=True, allow_null=True)
    svg_y = serializers.IntegerField(source='map_y', read_only=True, allow_null=True)
    occupancy_status = serializers.SerializerMethodField()

    class Meta:
        model = Stall
        fields = [
            'id', 'stall_number', 'section', 'section_name', 'section_code',
            'category', 'status', 'area_sqm', 'monthly_rent', 'vendor_name',
            'building', 'floor', 'svg_cell_id', 'svg_x', 'svg_y',
            'map_width', 'map_height', 'occupancy_status', 'vendor',
        ]

    def get_vendor_name(self, obj):
        return obj.vendor.full_name if hasattr(obj, 'vendor') and obj.vendor else None

    def get_vendor(self, obj):
        if hasattr(obj, 'vendor') and obj.vendor:
            return VendorPublicSerializer(obj.vendor).data
        return None

    def get_occupancy_status(self, obj):
        status_map = {
            'owner': 'occupied',
            'rented': 'occupied',
            'storage': 'storage',
            'surrendered_bolante': 'surrendered',
            'vacant': 'vacant',
            'closed': 'closed',
        }
        return status_map.get(obj.status, 'vacant')


class VendorSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    stall_number = serializers.CharField(source='stall.stall_number', read_only=True)
    section_name = serializers.CharField(source='stall.section.name', read_only=True)
    section_code = serializers.CharField(source='stall.section.code', read_only=True)
    stall_status = serializers.CharField(source='stall.status', read_only=True)
    products_list = serializers.ListField(read_only=True)
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    account_status = serializers.SerializerMethodField()

    class Meta:
        model = Vendor
        fields = ['id', 'user_id', 'first_name', 'last_name', 'full_name', 'email', 'phone',
                  'address', 'stall', 'stall_number', 'section_name', 'section_code',
                  'stall_status', 'products', 'products_list', 'permit_number',
                  'permit_expiry', 'health_cert_expiry', 'is_active',
                  'compliance_rate', 'joined_at', 'created_at', 'account_status']
        read_only_fields = ['id', 'created_at', 'compliance_rate']

    def get_account_status(self, obj):
        if not obj.user_id:
            return 'no_account'
        return 'pending_setup' if obj.user.must_change_password else 'active'


class VendorPublicSerializer(serializers.ModelSerializer):
    """
    Limited serializer for customer-role and unauthenticated access.
    Excludes personal contact details, permit numbers, expiry dates,
    compliance rates, and internal user IDs.
    Only exposes information a market visitor would legitimately need.
    """
    full_name = serializers.CharField(read_only=True)
    stall_number = serializers.CharField(source='stall.stall_number', read_only=True)
    section_name = serializers.CharField(source='stall.section.name', read_only=True)
    section_code = serializers.CharField(source='stall.section.code', read_only=True)
    products_list = serializers.ListField(read_only=True)

    class Meta:
        model = Vendor
        fields = ['id', 'full_name', 'stall_number', 'section_name', 'section_code',
                  'products_list', 'is_active']
        read_only_fields = ['id']

