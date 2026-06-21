from rest_framework import serializers
from .models import AIRiskProfile, AccomplishmentReport

class AIRiskProfileSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source='vendor.full_name', read_only=True)

    class Meta:
        model = AIRiskProfile
        fields = '__all__'

class AccomplishmentReportSerializer(serializers.ModelSerializer):
    generated_by_name = serializers.CharField(source='generated_by.get_full_name', read_only=True)

    class Meta:
        model = AccomplishmentReport
        fields = '__all__'
