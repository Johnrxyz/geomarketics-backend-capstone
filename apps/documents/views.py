from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.utils import timezone
from .models import Document
from .serializers import DocumentSerializer, DocumentReviewSerializer


class IsAdminRole(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'admin'


class DocumentViewSet(viewsets.ModelViewSet):
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'document_type', 'vendor']
    search_fields = ['title', 'vendor__first_name', 'vendor__last_name',
                     'vendor__stall__stall_number']
    ordering_fields = ['created_at', 'status', 'document_type', 'expiry_date']

    def get_queryset(self):
        user = self.request.user
        qs = Document.objects.select_related('vendor', 'vendor__stall', 'uploaded_by', 'reviewed_by').all()
        if user.role == 'vendor':
            if hasattr(user, 'vendor_profile'):
                return qs.filter(vendor=user.vendor_profile)
            return qs.none()
        return qs  # admin and customer-public browsing

    def get_serializer_class(self):
        return DocumentSerializer

    def get_permissions(self):
        if self.action in ['approve', 'reject']:
            return [IsAdminRole()]
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        user = self.request.user
        kwargs = {'uploaded_by': user}
        if user.role == 'vendor' and hasattr(user, 'vendor_profile'):
            kwargs['vendor'] = user.vendor_profile
        serializer.save(**kwargs)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        doc = self.get_object()
        doc.status = Document.STATUS_APPROVED
        doc.reviewed_by = request.user
        doc.reviewed_at = timezone.now()
        doc.review_notes = request.data.get('review_notes', '')
        doc.save()
        return Response(DocumentSerializer(doc).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        doc = self.get_object()
        doc.status = Document.STATUS_REJECTED
        doc.reviewed_by = request.user
        doc.reviewed_at = timezone.now()
        doc.review_notes = request.data.get('review_notes', '')
        doc.save()
        return Response(DocumentSerializer(doc).data)

    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        qs = self.get_queryset()
        return Response({
            'total': qs.count(),
            'pending': qs.filter(status='pending').count(),
            'approved': qs.filter(status='approved').count(),
            'rejected': qs.filter(status='rejected').count(),
            'expired': qs.filter(status='expired').count(),
        })
