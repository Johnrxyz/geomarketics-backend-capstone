from rest_framework import serializers
from .models import Violation, Penalty

class PenaltySerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Penalty
        fields = '__all__'

class ViolationSerializer(serializers.ModelSerializer):
    penalties = PenaltySerializer(many=True, read_only=True)
    vendor_name = serializers.CharField(source='vendor.full_name', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Violation
        fields = '__all__'
