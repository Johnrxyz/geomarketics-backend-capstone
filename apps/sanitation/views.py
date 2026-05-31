from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from .models import SanitationCheckItem, SanitationSession, SanitationRecord
from .serializers import (SanitationCheckItemSerializer, SanitationSessionSerializer,
                          SanitationSessionListSerializer, SanitationRecordSerializer)


class IsAdminRole(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'admin'


class SanitationSessionViewSet(viewsets.ModelViewSet):
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['section', 'date']
    ordering_fields = ['date', 'compliance_rate', 'created_at']

    def get_queryset(self):
        user = self.request.user
        qs = SanitationSession.objects.select_related('section', 'conducted_by').all()
        if user.role == 'vendor':
            # vendors can only see sessions where they were checked
            if hasattr(user, 'vendor_profile'):
                vendor = user.vendor_profile
                session_ids = SanitationRecord.objects.filter(vendor=vendor).values_list('session_id', flat=True)
                return qs.filter(pk__in=session_ids)
            return qs.none()
        return qs  # admin sees all

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return SanitationSessionSerializer
        return SanitationSessionListSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'bulk_save']:
            return [IsAdminRole()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        session = serializer.save(conducted_by=self.request.user)
        session.compliance_rate = session.calculate_compliance()
        session.save()

    @action(detail=True, methods=['post'], url_path='bulk-save')
    def bulk_save(self, request, pk=None):
        """Accept records array and upsert all sanitation check records for a session."""
        session = self.get_object()
        records_data = request.data.get('records', [])
        created, updated = 0, 0
        for item in records_data:
            obj, is_new = SanitationRecord.objects.update_or_create(
                session=session,
                vendor_id=item.get('vendor'),
                check_item_id=item.get('check_item'),
                defaults={
                    'status': item.get('status', 'na'),
                    'remarks': item.get('remarks', ''),
                }
            )
            if is_new:
                created += 1
            else:
                updated += 1
        session.compliance_rate = session.calculate_compliance()
        session.save()
        return Response({'created': created, 'updated': updated, 'compliance_rate': session.compliance_rate})

    @action(detail=False, methods=['get'], url_path='check-items')
    def check_items(self, request):
        items = SanitationCheckItem.objects.filter(is_active=True)
        return Response(SanitationCheckItemSerializer(items, many=True).data)


class SanitationRecordViewSet(viewsets.ModelViewSet):
    serializer_class = SanitationRecordSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['session', 'vendor', 'check_item', 'status']

    def get_queryset(self):
        user = self.request.user
        qs = SanitationRecord.objects.select_related('vendor', 'check_item', 'session').all()
        if user.role == 'vendor' and hasattr(user, 'vendor_profile'):
            return qs.filter(vendor=user.vendor_profile)
        return qs

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminRole()]
        return [permissions.IsAuthenticated()]
