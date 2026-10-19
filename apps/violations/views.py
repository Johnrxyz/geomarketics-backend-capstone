import logging

from django.db import transaction
from rest_framework.exceptions import APIException
from rest_framework import viewsets, permissions
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from .models import Violation, Penalty
from .serializers import ViolationSerializer, PenaltySerializer

logger = logging.getLogger(__name__)

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
        if getattr(user, 'role', '') == 'admin':
            return qs
        if getattr(user, 'role', '') == 'vendor':
            vendor = getattr(user, 'vendor_profile', None)
            return qs.filter(vendor=vendor) if vendor else qs.none()
        return qs.none()

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminRole()]
        return [permissions.IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except APIException:
            raise
        except Exception as exc:
            # Log only the exception class. Request payloads and exception
            # strings may contain submitted evidence or personal information.
            logger.error('Violation creation failed (error_type=%s).', type(exc).__name__)
            return Response(
                {'detail': 'Unable to create violation at this time.'},
                status=500,
            )

    def perform_create(self, serializer):
        from apps.notifications.models import Notification
        with transaction.atomic():
            violation = serializer.save(issued_by=self.request.user)

            # Keep the business record and its notice in one transaction.
            if violation.vendor and violation.vendor.user:
                Notification.objects.create(
                    recipient=violation.vendor.user,
                    notification_type=Notification.TYPE_WARNING,
                    title="Warning Letter Issued",
                    message=f"A violation has been recorded for your stall: {violation.violation_type}. Please check your dashboard for details.",
                    link="/vendor/violations",
                )

class PenaltyViewSet(viewsets.ModelViewSet):
    serializer_class = PenaltySerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status', 'violation']
    ordering_fields = ['due_date', 'created_at']

    def get_queryset(self):
        user = self.request.user
        qs = Penalty.objects.select_related('violation__vendor').all()
        if getattr(user, 'role', '') == 'admin':
            return qs
        if getattr(user, 'role', '') == 'vendor':
            vendor = getattr(user, 'vendor_profile', None)
            return qs.filter(violation__vendor=vendor) if vendor else qs.none()
        return qs.none()

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminRole()]
        return [permissions.IsAuthenticated()]
