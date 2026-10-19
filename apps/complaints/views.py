import logging
import mimetypes
from pathlib import Path

from django.db import transaction
from django.http import FileResponse
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.utils import timezone
from datetime import timedelta
from .models import Complaint, Blotter
from .serializers import ComplaintSerializer, ComplaintVendorSerializer, ComplaintCreateSerializer, BlotterSerializer
from apps.notifications.models import Notification
from django.contrib.auth import get_user_model
from utils.sms import notify_admins_sms
from apps.documents.storage import DocumentStorageUnavailable

User = get_user_model()
logger = logging.getLogger(__name__)


class IsAdminRole(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'admin'


class ComplaintViewSet(viewsets.ModelViewSet):
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'category', 'vendor', 'stall', 'complainant', 'is_flagged_spam']
    search_fields = ['complaint_number', 'subject', 'description', 'complainant_name',
                     'vendor__first_name', 'vendor__last_name', 'stall__stall_number']
    ordering_fields = ['created_at', 'status', 'category']

    def get_queryset(self):
        user = self.request.user
        qs = Complaint.objects.select_related('vendor', 'stall', 'complainant').all()
        if user.role == 'vendor':
            try:
                from django.db.models import Q
                return qs.filter(Q(vendor=user.vendor_profile) | Q(complainant=user))
            except Exception:
                return qs.none()
        if user.role == 'customer':
            return qs.filter(complainant=user)
        return qs  # admin sees all

    def get_serializer_class(self):
        if self.action == 'create':
            return ComplaintCreateSerializer
        # Vendors see complaint details but not complainant identity
        if hasattr(self.request, 'user') and getattr(self.request.user, 'role', None) == 'vendor':
            return ComplaintVendorSerializer
        return ComplaintSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.AllowAny()]
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsAdminRole()]
        return [permissions.IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            self.perform_create(serializer)
        except DocumentStorageUnavailable:
            return Response(
                {'detail': 'Evidence storage is unavailable. No public or local fallback was used.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=True, methods=['get'], url_path='evidence', url_name='evidence')
    def evidence(self, request, pk=None):
        complaint = self.get_object()
        user = request.user
        is_admin = getattr(user, 'role', None) == 'admin'
        is_complainant = complaint.complainant_id == user.pk
        is_target_vendor = False
        if getattr(user, 'role', None) == 'vendor':
            try:
                is_target_vendor = complaint.vendor_id == user.vendor_profile.pk
            except Exception:
                is_target_vendor = False
        if not (is_admin or is_complainant or is_target_vendor):
            return Response({'detail': 'You do not have permission to access this evidence.'}, status=403)

        evidence = complaint.evidence_file
        if not evidence:
            return Response({'detail': 'Complaint evidence not found.'}, status=404)
        try:
            file_handle = evidence.open('rb')
        except FileNotFoundError:
            return Response({'detail': 'Complaint evidence not found.'}, status=404)
        except DocumentStorageUnavailable:
            return Response({'detail': 'Complaint evidence storage is temporarily unavailable.'}, status=503)

        content_type = mimetypes.guess_type(Path(evidence.name).name)[0] or 'application/octet-stream'
        response = FileResponse(file_handle, content_type=content_type)
        response['X-Content-Type-Options'] = 'nosniff'
        disposition = 'attachment' if request.query_params.get('download') == '1' else 'inline'
        response['Content-Disposition'] = f'{disposition}; filename="{Path(evidence.name).name}"'
        response['Cache-Control'] = 'private, no-store'
        return response

    def retrieve(self, request, *args, **kwargs):
        """
        Override retrieve to enforce the same role-based queryset used by list().
        Without this, get_object() would bypass the role filter and allow any
        authenticated user to fetch any complaint by ID.
        """
        # get_queryset() already applies role-based filtering
        instance = self.get_queryset().filter(pk=kwargs['pk']).first()
        if instance is None:
            from rest_framework.exceptions import NotFound
            raise NotFound(detail="Complaint not found or you do not have permission to view it.")
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


    def perform_create(self, serializer):
        user = self.request.user
        kwargs = {}
        if user.is_authenticated:
            kwargs['complainant'] = user
            if user.role == 'vendor':
                try:
                    kwargs['vendor'] = user.vendor_profile
                except Exception:
                    pass

        # Auto-link vendor if stall is provided but vendor is not
        stall = serializer.validated_data.get('stall')
        vendor = serializer.validated_data.get('vendor')
        if stall and not vendor and 'vendor' not in kwargs:
            try:
                if hasattr(stall, 'vendor'):
                    kwargs['vendor'] = stall.vendor
            except Exception:
                pass

        storage_name = None
        try:
            with transaction.atomic():
                complaint = serializer.save(**kwargs)
                if complaint.evidence_file:
                    storage_name = complaint.evidence_file.name

                # ── Spam Detection ───────────────────────────────────────────
                window_start = timezone.now() - timedelta(hours=24)
                contact = complaint.complainant_contact or ""
                if contact:
                    recent_count = Complaint.objects.filter(
                        complainant_contact__iexact=contact,
                        created_at__gte=window_start
                    ).exclude(pk=complaint.pk).count()
                    if recent_count >= 2:
                        complaint.is_flagged_spam = True
                        complaint.spam_reason = (
                            f"Auto-flagged: {recent_count + 1} submissions from "
                            f"'{contact}' within 24 hours."
                        )
                        complaint.save(update_fields=['is_flagged_spam', 'spam_reason'])
                elif complaint.complainant:
                    recent_count = Complaint.objects.filter(
                        complainant=complaint.complainant,
                        created_at__gte=window_start
                    ).exclude(pk=complaint.pk).count()
                    if recent_count >= 2:
                        complaint.is_flagged_spam = True
                        complaint.spam_reason = (
                            f"Auto-flagged: {recent_count + 1} submissions from the "
                            f"same account within 24 hours."
                        )
                        complaint.save(update_fields=['is_flagged_spam', 'spam_reason'])

                category_display = dict(Complaint.CATEGORY_CHOICES).get(complaint.category, complaint.category)
                admins = User.objects.filter(role='admin')
                for admin in admins:
                    Notification.objects.create(
                        recipient=admin,
                        notification_type=Notification.TYPE_INFO,
                        title='New Complaint Filed',
                        message=f'A new complaint ({complaint.complaint_number}) has been filed regarding {category_display}.',
                        link='/admin/complaints'
                    )

                if complaint.vendor and hasattr(complaint.vendor, 'user') and complaint.vendor.user:
                    Notification.objects.create(
                        recipient=complaint.vendor.user,
                        notification_type=Notification.TYPE_WARNING,
                        title='Complaint Filed Against Your Stall',
                        message=(
                            f'A new complaint ({complaint.complaint_number}) has been filed against your stall '
                            f'regarding {category_display}. Please check the details.'
                        ),
                        link='/vendor/complaints'
                    )
        except Exception:
            # Cloudinary uploads happen before the database row is committed.
            # Compensate if this transaction rolls back after the asset upload.
            if storage_name is None and serializer.instance and serializer.instance.evidence_file:
                stored_file = serializer.instance.evidence_file
                if getattr(stored_file, '_committed', False):
                    storage_name = stored_file.name
            if storage_name:
                try:
                    Complaint._meta.get_field('evidence_file').storage.delete(storage_name)
                except Exception:
                    logger.error('Failed to clean up complaint evidence after transaction rollback.')
            raise


    def _notify_complaint_status_change(self, complaint, old_status):
        if old_status == complaint.status:
            return

        status_display = dict(Complaint.STATUS_CHOICES).get(complaint.status, complaint.status)
        message = f'Complaint {complaint.complaint_number} status changed to {status_display}.'
        recipients = {}
        if complaint.complainant_id:
            recipients[complaint.complainant_id] = (
                complaint.complainant,
                'Complaint Status Updated',
                '/vendor/complaints' if complaint.complainant.role == 'vendor' else '/complaints',
                Notification.TYPE_INFO,
            )
        if complaint.vendor_id and complaint.vendor and complaint.vendor.user_id:
            recipients[complaint.vendor.user_id] = (
                complaint.vendor.user,
                'Complaint Against Stall Updated',
                '/vendor/complaints',
                Notification.TYPE_INFO,
            )

        for recipient, title, link, notification_type in recipients.values():
            Notification.objects.create(
                recipient=recipient,
                notification_type=notification_type,
                title=title,
                message=message,
                link=link,
            )

    def perform_update(self, serializer):
        old_status = serializer.instance.status
        with transaction.atomic():
            complaint = serializer.save()
            self._notify_complaint_status_change(complaint, old_status)

    @action(detail=True, methods=['patch'], url_path='update-status')
    def update_status(self, request, pk=None):
        if request.user.role != 'admin':
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        complaint = self.get_object()
        new_status = request.data.get('status')
        resolution_notes = request.data.get('resolution_notes', complaint.resolution_notes)
        if new_status not in dict(Complaint.STATUS_CHOICES):
            return Response({'detail': 'Invalid status.'}, status=status.HTTP_400_BAD_REQUEST)
        
        old_status = complaint.status
        with transaction.atomic():
            complaint.status = new_status
            complaint.resolution_notes = resolution_notes
            if new_status == Complaint.STATUS_RESOLVED:
                complaint.resolved_at = timezone.now()
                complaint.resolved_by = request.user
            complaint.save()
            self._notify_complaint_status_change(complaint, old_status)

        return Response(ComplaintSerializer(complaint).data)

    @action(detail=True, methods=['patch'], url_path='flag-spam')
    def flag_spam(self, request, pk=None):
        """Admin can manually flag or unflag a complaint as spam."""
        if request.user.role != 'admin':
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        complaint = self.get_object()
        flag = request.data.get('is_flagged_spam')
        reason = request.data.get('spam_reason', '')
        if flag is None:
            return Response({'detail': 'is_flagged_spam field required.'}, status=status.HTTP_400_BAD_REQUEST)
        complaint.is_flagged_spam = bool(flag)
        complaint.spam_reason = reason if flag else ''
        complaint.save(update_fields=['is_flagged_spam', 'spam_reason'])
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

    @action(detail=True, methods=['post'], url_path='escalate')
    def escalate(self, request, pk=None):
        if request.user.role != 'admin':
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        complaint = self.get_object()
        if hasattr(complaint, 'blotter') and complaint.blotter:
            return Response({'detail': 'Already escalated.'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Build complainant name
        c_name = complaint.complainant_name
        if not c_name and complaint.complainant:
            c_name = complaint.complainant.get_full_name() or complaint.complainant.username
            
        blotter = Blotter.objects.create(
            complaint=complaint,
            incident_date=complaint.created_at,
            recorded_by=request.user,
            vendor=complaint.vendor,
            complainant_name=c_name,
            incident_details=complaint.description,
            status='open'
        )
        # Import inside to avoid circular import if serializers get messy, but BlotterSerializer is at top
        return Response(BlotterSerializer(blotter).data, status=status.HTTP_201_CREATED)


class BlotterViewSet(viewsets.ModelViewSet):
    serializer_class = BlotterSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'vendor']
    search_fields = ['complainant_name', 'incident_details', 'action_taken', 'vendor__first_name', 'vendor__last_name']
    ordering_fields = ['incident_date', 'created_at']

    def get_queryset(self):
        user = self.request.user
        qs = Blotter.objects.select_related('vendor', 'recorded_by').all()
        if getattr(user, 'role', '') == 'vendor':
            try:
                return qs.filter(vendor=user.vendor_profile)
            except Exception:
                return qs.none()
        return qs

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminRole()]
        return [permissions.IsAuthenticated()]
