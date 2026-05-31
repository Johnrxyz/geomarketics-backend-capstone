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

    class Meta:
        model = Stall
        fields = ['id', 'stall_number', 'section', 'section_name', 'section_code',
                  'category', 'status', 'area_sqm', 'monthly_rent', 'vendor_name']

    def get_vendor_name(self, obj):
        if hasattr(obj, 'vendor') and obj.vendor:
            return obj.vendor.full_name
        return None


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


class VendorSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    stall_number = serializers.CharField(source='stall.stall_number', read_only=True)
    section_name = serializers.CharField(source='stall.section.name', read_only=True)
    section_code = serializers.CharField(source='stall.section.code', read_only=True)
    stall_status = serializers.CharField(source='stall.status', read_only=True)
    products_list = serializers.ListField(read_only=True)

    class Meta:
        model = Vendor
        fields = ['id', 'first_name', 'last_name', 'full_name', 'email', 'phone',
                  'address', 'stall', 'stall_number', 'section_name', 'section_code',
                  'stall_status', 'products', 'products_list', 'permit_number',
                  'permit_expiry', 'health_cert_expiry', 'is_active',
                  'compliance_rate', 'joined_at', 'created_at']
        read_only_fields = ['id', 'created_at', 'compliance_rate']
