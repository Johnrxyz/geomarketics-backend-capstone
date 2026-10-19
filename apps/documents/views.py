import mimetypes
import logging
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.http import FileResponse
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response

from apps.notifications.models import Notification
from .models import Document, DocumentPage, DocumentReview
from .serializers import DocumentSerializer
from .services.upload_validation import validate_document_upload
from .storage import DocumentStorageUnavailable
from .tasks import process_uploaded_document
from core.tasks import run_task_async

logger = logging.getLogger(__name__)


def _cleanup_storage_names(names):
    for name in dict.fromkeys(filter(None, names)):
        try:
            Document._meta.get_field('file').storage.delete(name)
        except Exception:
            # The storage adapter logs only the generated Cloudinary ID. Keep
            # rollback cleanup best-effort so one failed delete does not skip
            # cleanup attempts for other assets from the same transaction.
            logger.error('Failed to clean up document storage key %s.', name)


class IsAdminRole(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'admin'


class IsVendorRole(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'vendor' and hasattr(request.user, 'vendor_profile')


class DocumentViewSet(viewsets.ModelViewSet):
    serializer_class = DocumentSerializer
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    http_method_names = ['get', 'post', 'head', 'options']
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'document_type', 'vendor']
    search_fields = ['title', 'vendor__first_name', 'vendor__last_name', 'vendor__stall__stall_number']
    ordering_fields = ['created_at', 'status', 'document_type', 'expiry_date']

    def get_queryset(self):
        user = self.request.user
        qs = Document.objects.select_related('vendor', 'vendor__stall', 'uploaded_by', 'reviewed_by').prefetch_related('pages', 'review_history__reviewed_by')
        if not user.is_authenticated:
            return qs.none()
        if user.role == 'admin':
            return qs.all()
        if user.role == 'vendor' and hasattr(user, 'vendor_profile'):
            return qs.filter(vendor=user.vendor_profile)
        return qs.none()

    def get_permissions(self):
        if self.action in ['approve', 'reject', 'request_resubmission']:
            return [IsAdminRole()]
        if self.action in ['create', 'add_page', 'submit_contract']:
            return [IsVendorRole()]
        if self.action in ['list', 'retrieve', 'file', 'page_file', 'summary']:
            return [permissions.IsAuthenticated()]
        return [IsAdminRole()]

    def perform_create(self, serializer):
        user = self.request.user
        vendor = user.vendor_profile
        document_type = serializer.validated_data['document_type']
        is_contract = document_type == Document.TYPE_CONTRACT
        pages = self.request.FILES.getlist('pages')
        for upload in pages:
            validate_document_upload(upload)
        upload = serializer.validated_data.get('file')

        created_file_names = []
        document = None
        try:
            with transaction.atomic():
                document = serializer.save(
                    vendor=vendor,
                    uploaded_by=user,
                    status=Document.STATUS_INCOMPLETE if is_contract else Document.STATUS_PENDING,
                    ocr_status='pending' if settings.DOCUMENT_PROCESSING_MODE == 'ocr' else 'skipped',
                    file_size=f'{upload.size / (1024 * 1024):.2f} MB' if upload else '',
                )
                if is_contract:
                    for i, page_file in enumerate(pages):
                        page = DocumentPage(document=document, page_upload_order=i + 1)
                        page.file.save(page_file.name, page_file, save=False)
                        created_file_names.append(page.file.name)
                        page.save()
                elif document.file:
                    DocumentPage.objects.create(document=document, file=document.file, page_upload_order=1)
                    if settings.DOCUMENT_PROCESSING_MODE == 'ocr':
                        document.status = Document.STATUS_PROCESSING
                        document.save(update_fields=['status'])
                        transaction.on_commit(lambda: run_task_async(process_uploaded_document, document.id))
        except Exception:
            if document and document.file:
                created_file_names.append(document.file.name)
            _cleanup_storage_names(created_file_names)
            raise

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            self.perform_create(serializer)
        except DocumentStorageUnavailable:
            return Response({'detail': 'Document storage is unavailable. No local fallback was used.'}, status=503)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def _review(self, doc, request, new_status):
        notes = request.data.get('review_notes', '')
        if doc.status != Document.STATUS_PENDING:
            return Response({'detail': 'Only documents pending review can be reviewed.'}, status=status.HTTP_400_BAD_REQUEST)
        if new_status in [Document.STATUS_REJECTED, Document.STATUS_RESUBMISSION] and not str(notes).strip():
            return Response({'review_notes': 'A note is required when rejecting or requesting resubmission.'}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            doc.status = new_status
            doc.reviewed_by = request.user
            doc.reviewed_at = timezone.now()
            doc.review_notes = notes
            doc.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_notes', 'updated_at'])
            DocumentReview.objects.create(document=doc, status=new_status, notes=notes, reviewed_by=request.user)

            if doc.vendor and doc.vendor.user:
                notification_type, title, message = {
                    Document.STATUS_APPROVED: (
                        Notification.TYPE_SUCCESS, 'Document Approved',
                        f"Your document '{doc.title}' has been approved.",
                    ),
                    Document.STATUS_REJECTED: (
                        Notification.TYPE_ERROR, 'Document Rejected',
                        f"Your document '{doc.title}' has been rejected. Reason: {notes}",
                    ),
                    Document.STATUS_RESUBMISSION: (
                        Notification.TYPE_WARNING, 'Document Resubmission Required',
                        f"Please resubmit your document '{doc.title}'. Note: {notes}",
                    ),
                }[new_status]
                Notification.objects.create(recipient=doc.vendor.user, notification_type=notification_type,
                                            title=title, message=message, link='/vendor/documents')
        doc.refresh_from_db()
        return Response(self.get_serializer(doc).data)

    def _document_response(self, request, doc, page=None):
        field = page.file if page else doc.file
        if not field:
            return Response({'detail': 'Document file not found.'}, status=status.HTTP_404_NOT_FOUND)
        content_type = mimetypes.guess_type(Path(field.name).name)[0] or 'application/octet-stream'
        try:
            file_handle = field.open('rb')
        except FileNotFoundError:
            return Response({'detail': 'Document file not found.'}, status=404)
        except DocumentStorageUnavailable:
            return Response({'detail': 'Document storage is temporarily unavailable.'}, status=503)
        response = FileResponse(file_handle, content_type=content_type)
        response['X-Content-Type-Options'] = 'nosniff'
        disposition = 'attachment' if request.query_params.get('download') == '1' else 'inline'
        response['Content-Disposition'] = f'{disposition}; filename="{Path(field.name).name}"'
        response['Cache-Control'] = 'private, no-store'
        return response

    @action(detail=True, methods=['get'], url_path='file', url_name='file')
    def file(self, request, pk=None):
        return self._document_response(request, self.get_object())

    @action(detail=True, methods=['get'], url_path=r'pages/(?P<page_id>[^/.]+)/file', url_name='page-file')
    def page_file(self, request, pk=None, page_id=None):
        doc = self.get_object()
        page = doc.pages.filter(pk=page_id).first()
        if page is None:
            return Response({'detail': 'Document page not found.'}, status=status.HTTP_404_NOT_FOUND)
        return self._document_response(request, doc, page)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        return self._review(self.get_object(), request, Document.STATUS_APPROVED)

    @action(detail=True, methods=['post'], url_path='add-page')
    def add_page(self, request, pk=None):
        doc = self.get_object()
        if doc.document_type != Document.TYPE_CONTRACT:
            return Response({'error': 'Only contract documents support page uploads.'}, status=400)
        if doc.status not in [Document.STATUS_INCOMPLETE, Document.STATUS_RESUBMISSION]:
            return Response({'error': 'This document is no longer accepting new pages.'}, status=400)
        page_file = request.FILES.get('page')
        if not page_file:
            return Response({'error': 'No file provided.'}, status=400)
        validate_document_upload(page_file)
        upload_order = doc.pages.count() + 1
        if upload_order > 3:
            return Response({'error': 'Contract supports exactly three pages.'}, status=400)
        page = DocumentPage(document=doc, page_upload_order=upload_order)
        try:
            page.file.save(page_file.name, page_file, save=False)
            with transaction.atomic():
                page.save()
        except DocumentStorageUnavailable:
            return Response({'detail': 'Document storage is unavailable. No local fallback was used.'}, status=503)
        except Exception:
            try:
                page.file.delete(save=False)
            except Exception:
                pass
            raise
        return Response({'pages_uploaded': doc.pages.count(), 'pages_required': 3, 'ready_to_submit': doc.pages.count() == 3})

    @action(detail=True, methods=['post'], url_path='submit-contract')
    def submit_contract(self, request, pk=None):
        doc = self.get_object()
        if doc.document_type != Document.TYPE_CONTRACT:
            return Response({'error': 'Only contract documents can be submitted this way.'}, status=400)
        if doc.status not in [Document.STATUS_INCOMPLETE, Document.STATUS_RESUBMISSION]:
            return Response({'error': 'This document has already been submitted.'}, status=400)
        page_count = doc.pages.count()
        if page_count != 3:
            return Response({'error': f'Contract requires 3 pages. {page_count} uploaded, {3 - page_count} missing.',
                             'pages_uploaded': page_count, 'pages_required': 3}, status=400)
        if settings.DOCUMENT_PROCESSING_MODE == 'ocr':
            doc.status = Document.STATUS_PROCESSING
            doc.ocr_status = 'pending'
            doc.save(update_fields=['status', 'ocr_status', 'updated_at'])
            run_task_async(process_uploaded_document, doc.id)
            return Response({'message': 'Contract submitted for processing.', 'status': doc.status})
        doc.status = Document.STATUS_PENDING
        doc.ocr_status = 'skipped'
        doc.save(update_fields=['status', 'ocr_status', 'updated_at'])
        return Response({'message': 'Contract submitted for review.', 'status': doc.status})

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        return self._review(self.get_object(), request, Document.STATUS_REJECTED)

    @action(detail=True, methods=['post'], url_path='request_resubmission')
    def request_resubmission(self, request, pk=None):
        return self._review(self.get_object(), request, Document.STATUS_RESUBMISSION)

    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        qs = self.get_queryset()
        return Response({'total': qs.count(), 'pending': qs.filter(status='pending').count(),
                         'approved': qs.filter(status='approved').count(), 'rejected': qs.filter(status='rejected').count(),
                         'expired': qs.filter(status='expired').count()})
