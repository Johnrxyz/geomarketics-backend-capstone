from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.utils import timezone
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from .models import Document
from .serializers import DocumentSerializer, DocumentReviewSerializer
from apps.documents.services.validation import validate_image_quality
from apps.documents.tasks import process_uploaded_document
from core.tasks import run_task_async
from apps.notifications.models import Notification


class IsAdminRole(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'admin'


class DocumentViewSet(viewsets.ModelViewSet):
    parser_classes = (MultiPartParser, FormParser, JSONParser)
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
            
        document = serializer.save(**kwargs)
        
        from apps.documents.models import DocumentPage
        is_contract = document.document_type == 'contract'
        pages = self.request.FILES.getlist('pages')
        
        if is_contract:
            # Contracts use the multi-page pages[] flow and start INCOMPLETE
            if pages:
                for i, page_file in enumerate(pages):
                    DocumentPage.objects.create(
                        document=document,
                        file=page_file,
                        page_upload_order=i+1
                    )
            # Contracts stay INCOMPLETE until all 3 pages are present
        else:
            # Business Permits: single-file upload, immediately kick off OCR
            if document.file:
                DocumentPage.objects.create(
                    document=document,
                    file=document.file,
                    page_upload_order=1
                )
            # Trigger async OCR, Classification, and Validation
            document.status = 'processing'
            document.save(update_fields=['status'])
            run_task_async(process_uploaded_document, document.id)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        doc = self.get_object()
        doc.status = Document.STATUS_APPROVED
        doc.reviewed_by = request.user
        doc.reviewed_at = timezone.now()
        doc.review_notes = request.data.get('review_notes', '')
        doc.save()
        
        if doc.vendor and doc.vendor.user:
            Notification.objects.create(
                recipient=doc.vendor.user,
                notification_type=Notification.TYPE_SUCCESS,
                title="Document Approved",
                message=f"Your document '{doc.title}' has been approved.",
                link="/vendor/documents"
            )
            
        return Response(DocumentSerializer(doc).data)

    @action(detail=True, methods=['post'], url_path='add-page')
    def add_page(self, request, pk=None):
        """
        Adds a single page file to an existing INCOMPLETE contract document.
        Vendors can call this multiple times to build up the 3 required pages.
        The page is saved but OCR is NOT triggered yet — that happens on submit.
        """
        from apps.documents.models import DocumentPage
        doc = self.get_object()

        if doc.document_type != 'contract':
            return Response({'error': 'Only contract documents support page uploads.'}, status=400)
        if doc.status not in ['incomplete', 'resubmission_required']:
            return Response({'error': 'This document is no longer accepting new pages.'}, status=400)

        page_file = request.FILES.get('page')
        if not page_file:
            return Response({'error': 'No file provided.'}, status=400)

        upload_order = doc.pages.count() + 1
        DocumentPage.objects.create(
            document=doc,
            file=page_file,
            page_upload_order=upload_order
        )

        # Return updated page count
        return Response({
            'pages_uploaded': doc.pages.count(),
            'pages_required': 3,
            'ready_to_submit': doc.pages.count() >= 3
        })

    @action(detail=True, methods=['post'], url_path='submit-contract')
    def submit_contract(self, request, pk=None):
        """
        Submits a contract for OCR processing after all 3 pages have been uploaded.
        Validates that exactly 3 pages are present before triggering OCR.
        """
        doc = self.get_object()

        if doc.document_type != 'contract':
            return Response({'error': 'Only contract documents can be submitted this way.'}, status=400)
        if doc.status not in ['incomplete', 'resubmission_required']:
            return Response({'error': 'This document has already been submitted.'}, status=400)

        page_count = doc.pages.count()
        if page_count < 3:
            missing = 3 - page_count
            return Response({
                'error': f'Contract requires 3 pages. {page_count} uploaded, {missing} missing.',
                'pages_uploaded': page_count,
                'pages_required': 3
            }, status=400)

        # Transition to PROCESSING and kick off OCR
        doc.status = 'processing'
        doc.save(update_fields=['status'])
        run_task_async(process_uploaded_document, doc.id)

        return Response({'message': 'Contract submitted for review.', 'status': 'processing'})


    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        doc = self.get_object()
        doc.status = Document.STATUS_REJECTED
        doc.reviewed_by = request.user
        doc.reviewed_at = timezone.now()
        doc.review_notes = request.data.get('review_notes', '')
        doc.save()
        
        if doc.vendor and doc.vendor.user:
            Notification.objects.create(
                recipient=doc.vendor.user,
                notification_type=Notification.TYPE_ERROR,
                title="Document Rejected",
                message=f"Your document '{doc.title}' has been rejected. Reason: {doc.review_notes}",
                link="/vendor/documents"
            )
            
        return Response(DocumentSerializer(doc).data)
        
    @action(detail=True, methods=['post'])
    def request_resubmission(self, request, pk=None):
        doc = self.get_object()
        doc.status = Document.STATUS_RESUBMISSION
        doc.reviewed_by = request.user
        doc.reviewed_at = timezone.now()
        doc.review_notes = request.data.get('review_notes', '')
        doc.save()
        
        if doc.vendor and doc.vendor.user:
            Notification.objects.create(
                recipient=doc.vendor.user,
                notification_type=Notification.TYPE_WARNING,
                title="Document Resubmission Required",
                message=f"Please resubmit your document '{doc.title}'. Note: {doc.review_notes}",
                link="/vendor/documents"
            )
            
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
