from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.utils import timezone
from .models import Complaint
from .serializers import ComplaintSerializer, ComplaintCreateSerializer


class IsAdminRole(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'admin'


class ComplaintViewSet(viewsets.ModelViewSet):
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'category', 'vendor', 'stall']
    search_fields = ['complaint_number', 'subject', 'description', 'complainant_name',
                     'vendor__first_name', 'vendor__last_name', 'stall__stall_number']
    ordering_fields = ['created_at', 'status', 'category']

    def get_queryset(self):
        user = self.request.user
        qs = Complaint.objects.select_related('vendor', 'stall', 'complainant').all()
        if user.role == 'vendor':
            if hasattr(user, 'vendor_profile'):
                return qs.filter(vendor=user.vendor_profile)
            return qs.none()
        if user.role == 'customer':
            return qs.filter(complainant=user)
        return qs  # admin sees all

    def get_serializer_class(self):
        if self.action == 'create':
            return ComplaintCreateSerializer
        return ComplaintSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.IsAuthenticated()]
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsAdminRole()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        user = self.request.user
        kwargs = {'complainant': user}
        if user.role == 'vendor' and hasattr(user, 'vendor_profile'):
            kwargs['vendor'] = user.vendor_profile
        serializer.save(**kwargs)

    @action(detail=True, methods=['patch'], url_path='update-status')
    def update_status(self, request, pk=None):
        if request.user.role != 'admin':
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        complaint = self.get_object()
        new_status = request.data.get('status')
        admin_notes = request.data.get('admin_notes', complaint.admin_notes)
        if new_status not in dict(Complaint.STATUS_CHOICES):
            return Response({'detail': 'Invalid status.'}, status=status.HTTP_400_BAD_REQUEST)
        complaint.status = new_status
        complaint.admin_notes = admin_notes
        if new_status == Complaint.STATUS_RESOLVED:
            complaint.resolved_at = timezone.now()
            complaint.resolved_by = request.user
        complaint.save()
        return Response(ComplaintSerializer(complaint).data)

    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        qs = self.get_queryset()
        return Response({
            'total': qs.count(),
            'open': qs.filter(status='open').count(),
            'reviewing': qs.filter(status='reviewing').count(),
            'resolved': qs.filter(status='resolved').count(),
            'dismissed': qs.filter(status='dismissed').count(),
        })
