from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Count, Q
from django.db import transaction
from django.utils.text import slugify
import secrets
from .models import MarketSection, Stall, Vendor
from .serializers import (
    MarketSectionSerializer,
    StallListSerializer,
    StallDetailSerializer,
    StallPublicDetailSerializer,
    VendorSerializer,
    VendorPublicSerializer,
)


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
            user = self.request.user
            if user.is_authenticated and getattr(user, 'role', None) == 'admin':
                return StallDetailSerializer
            return StallPublicDetailSerializer
        return StallListSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [IsAdminRole()]

    @action(detail=False, methods=['get'], url_path='alert-summary', permission_classes=[IsAdminRole])
    def alert_summary(self, request):
        """
        Returns one record per stall that has open complaints or active violations.
        Each record contains an 'alerts' array so a stall can have both types simultaneously.
        No new DB tables — queries existing Complaint and Violation models via FK relationships.
        """
        from apps.complaints.models import Complaint
        from apps.violations.models import Violation

        # ── Open / reviewing complaints grouped by stall ──────────────────
        complaint_qs = (
            Complaint.objects
            .filter(
                stall__isnull=False,
                status__in=[Complaint.STATUS_OPEN, Complaint.STATUS_REVIEWING],
                is_flagged_spam=False,
            )
            .values('stall__id', 'stall__stall_number', 'stall__svg_cell_id', 'stall__building', 'stall__floor')
            .annotate(count=Count('id'))
        )

        # ── Active violations grouped by vendor → stall ───────────────────
        violation_qs = (
            Violation.objects
            .filter(
                status=Violation.STATUS_ACTIVE,
                vendor__stall__isnull=False,
            )
            .values(
                'vendor__stall__id',
                'vendor__stall__stall_number',
                'vendor__stall__svg_cell_id',
                'vendor__stall__building',
                'vendor__stall__floor',
            )
            .annotate(count=Count('id'))
        )

        # ── Merge into one dict keyed by stall DB id ──────────────────────
        merged: dict = {}

        for row in complaint_qs:
            sid = row['stall__id']
            if sid not in merged:
                merged[sid] = {
                    'stall_db_id': sid,
                    'stall_number': row['stall__stall_number'],
                    'svg_cell_id': row['stall__svg_cell_id'] or '',
                    'building': row['stall__building'],
                    'floor': row['stall__floor'],
                    'alerts': [],
                }
            merged[sid]['alerts'].append({
                'type': 'complaint',
                'severity': 'medium',   # complaint open/reviewing — orange in UI
                'count': row['count'],
            })

        for row in violation_qs:
            sid = row['vendor__stall__id']
            if sid not in merged:
                merged[sid] = {
                    'stall_db_id': sid,
                    'stall_number': row['vendor__stall__stall_number'],
                    'svg_cell_id': row['vendor__stall__svg_cell_id'] or '',
                    'building': row['vendor__stall__building'],
                    'floor': row['vendor__stall__floor'],
                    'alerts': [],
                }
            merged[sid]['alerts'].append({
                'type': 'violation',
                'severity': 'high',     # active violation — red in UI
                'count': row['count'],
            })

        return Response(list(merged.values()))


class VendorViewSet(viewsets.ModelViewSet):
    serializer_class = VendorSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['is_active', 'stall__section', 'stall__status']
    search_fields = ['first_name', 'last_name', 'email', 'stall__stall_number']
    ordering_fields = ['last_name', 'first_name', 'created_at', 'compliance_rate']

    def get_serializer_class(self):
        """
        Return a limited public serializer for customer-role users so that
        personal contact details, permit data, and compliance rates are not
        disclosed to market shoppers.  Admin and vendor users receive the full
        serializer.
        """
        user = self.request.user
        if user.is_authenticated and getattr(user, 'role', None) == 'customer':
            return VendorPublicSerializer
        return VendorSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Vendor.objects.select_related('stall', 'stall__section', 'user').all()
        if user.role == 'vendor':
            try:
                return qs.filter(pk=user.vendor_profile.pk)
            except Exception:
                return qs.none()
        if user.role == 'customer':
            return qs.filter(is_active=True)
        return qs  # admin sees all

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            from apps.users.permissions import PasswordSetupPermission
            return [PasswordSetupPermission()]
        return [IsAdminRole()]

    def _create_login_account(self, vendor):
        if vendor.user_id:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'account': 'This vendor already has a linked login account.'})
        from apps.users.models import User
        base = slugify(f'{vendor.first_name}.{vendor.last_name}').replace('-', '.') or 'vendor'
        while True:
            username = f'{base}.{secrets.token_hex(3)}'
            if not User.objects.filter(username__iexact=username).exists():
                break
        temporary_password = secrets.token_urlsafe(18)
        user = User(
            username=username,
            email=vendor.email.strip(),
            first_name=vendor.first_name,
            last_name=vendor.last_name,
            phone=vendor.phone,
            role=User.ROLE_VENDOR,
            must_change_password=True,
        )
        user.set_password(temporary_password)
        user.save()
        vendor.user = user
        vendor.save(update_fields=['user', 'updated_at'])
        return {'username': username, 'temporary_password': temporary_password}

    def create(self, request, *args, **kwargs):
        create_account = request.data.get('create_account', False)
        if isinstance(create_account, str):
            create_account = create_account.lower() in ('true', '1', 'yes')
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            vendor = serializer.save()
            credentials = self._create_login_account(vendor) if create_account else None
        data = self.get_serializer(vendor).data
        if credentials:
            data['credentials'] = credentials
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='create-account', permission_classes=[IsAdminRole])
    def create_account(self, request, pk=None):
        with transaction.atomic():
            vendor = self.get_object()
            credentials = self._create_login_account(vendor)
        return Response({'vendor': self.get_serializer(vendor).data, 'credentials': credentials}, status=status.HTTP_201_CREATED)

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
