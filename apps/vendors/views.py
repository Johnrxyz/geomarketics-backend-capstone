from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from .models import MarketSection, Stall, Vendor
from .serializers import MarketSectionSerializer, StallListSerializer, StallDetailSerializer, VendorSerializer


class IsAdminRole(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'admin'


class IsAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated
        return request.user.is_authenticated and request.user.role == 'admin'


class MarketSectionViewSet(viewsets.ModelViewSet):
    queryset = MarketSection.objects.all()
    serializer_class = MarketSectionSerializer
    permission_classes = [IsAdminOrReadOnly]
    search_fields = ['name', 'code']
    ordering_fields = ['code', 'name']


class StallViewSet(viewsets.ModelViewSet):
    queryset = Stall.objects.select_related('section', 'vendor').all()
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['section', 'status', 'category']
    search_fields = ['stall_number', 'category', 'vendor__first_name', 'vendor__last_name']
    ordering_fields = ['stall_number', 'status', 'section']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return StallDetailSerializer
        return StallListSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [IsAdminRole()]


class VendorViewSet(viewsets.ModelViewSet):
    serializer_class = VendorSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['is_active', 'stall__section', 'stall__status']
    search_fields = ['first_name', 'last_name', 'email', 'stall__stall_number']
    ordering_fields = ['last_name', 'first_name', 'created_at', 'compliance_rate']

    def get_queryset(self):
        user = self.request.user
        qs = Vendor.objects.select_related('stall', 'stall__section', 'user').all()
        if user.role == 'vendor':
            if hasattr(user, 'vendor_profile'):
                return qs.filter(pk=user.vendor_profile.pk)
            return qs.none()
        if user.role == 'customer':
            return qs.filter(is_active=True)
        return qs  # admin sees all

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        return [IsAdminRole()]

    @action(detail=True, methods=['get'], url_path='compliance-history')
    def compliance_history(self, request, pk=None):
        from apps.sanitation.models import SanitationRecord
        from apps.sanitation.serializers import SanitationRecordSerializer
        vendor = self.get_object()
        records = SanitationRecord.objects.filter(vendor=vendor).select_related(
            'session', 'check_item'
        ).order_by('-session__date')[:50]
        return Response(SanitationRecordSerializer(records, many=True).data)

    @action(detail=True, methods=['get'], url_path='compliance-profile')
    def compliance_profile(self, request, pk=None):
        from apps.documents.services.compliance import VendorComplianceService
        vendor = self.get_object()
        compliance_data = VendorComplianceService.evaluate_vendor(vendor)
        return Response(compliance_data)
