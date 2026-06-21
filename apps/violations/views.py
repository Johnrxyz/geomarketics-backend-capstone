from rest_framework import viewsets, permissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from .models import Violation, Penalty
from .serializers import ViolationSerializer, PenaltySerializer

class IsAdminRole(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'admin'

class ViolationViewSet(viewsets.ModelViewSet):
    serializer_class = ViolationSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'severity', 'vendor']
    search_fields = ['violation_type', 'description', 'vendor__first_name', 'vendor__last_name']
    ordering_fields = ['violation_date', 'created_at']

    def get_queryset(self):
        user = self.request.user
        qs = Violation.objects.select_related('vendor').prefetch_related('penalties').all()
        if getattr(user, 'role', '') == 'vendor' and hasattr(user, 'vendor_profile'):
            return qs.filter(vendor=user.vendor_profile)
        return qs

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminRole()]
        return [permissions.IsAuthenticated()]

class PenaltyViewSet(viewsets.ModelViewSet):
    serializer_class = PenaltySerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status', 'violation']
    ordering_fields = ['due_date', 'created_at']

    def get_queryset(self):
        user = self.request.user
        qs = Penalty.objects.select_related('violation__vendor').all()
        if getattr(user, 'role', '') == 'vendor' and hasattr(user, 'vendor_profile'):
            return qs.filter(violation__vendor=user.vendor_profile)
        return qs

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminRole()]
        return [permissions.IsAuthenticated()]
