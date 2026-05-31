from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from django.db.models import Count, Q, Avg
from django.utils import timezone
from datetime import timedelta, date

from apps.vendors.models import MarketSection, Stall, Vendor
from apps.complaints.models import Complaint
from apps.documents.models import Document
from apps.prices.models import PriceReport, PriceEntry


class IsAdminRole(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'admin'


class DashboardView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        total_stalls = Stall.objects.count()
        occupied_stalls = Stall.objects.filter(status='occupied').count()
        active_vendors = Vendor.objects.filter(is_active=True).count()
        open_complaints = Complaint.objects.filter(status='open').count()
        pending_documents = Document.objects.filter(status='pending').count()

        # Occupancy by section
        sections = MarketSection.objects.annotate(
            total=Count('stalls'),
            occupied=Count('stalls', filter=Q(stalls__status='occupied'))
        ).values('code', 'name', 'total', 'occupied')

        section_data = []
        for s in sections:
            rate = round((s['occupied'] / s['total'] * 100), 1) if s['total'] > 0 else 0
            section_data.append({
                'section': s['code'],
                'name': s['name'],
                'total': s['total'],
                'occupied': s['occupied'],
                'occupancy_rate': rate,
            })

        # Complaints by category
        complaint_by_category = list(
            Complaint.objects.values('category').annotate(count=Count('id'))
            .order_by('-count')
        )

        # Recent complaints
        recent_complaints = Complaint.objects.select_related('vendor', 'stall').order_by('-created_at')[:5]
        recent_data = [{
            'id': c.id,
            'complaint_number': c.complaint_number,
            'subject': c.subject,
            'category': c.category,
            'status': c.status,
            'vendor_name': c.vendor.full_name if c.vendor else c.complainant_name,
            'stall_number': c.stall.stall_number if c.stall else None,
            'created_at': c.created_at.isoformat(),
        } for c in recent_complaints]

        # Price trend (last 6 weeks of reports)
        reports = PriceReport.objects.filter(is_published=True).order_by('-report_date')[:6]
        price_trend = []
        for r in reversed(list(reports)):
            veg_avg = PriceEntry.objects.filter(
                report=r, commodity__category__name__icontains='Vegetable'
            ).aggregate(avg=Avg('average_price'))['avg']
            meat_avg = PriceEntry.objects.filter(
                report=r, commodity__category__name__icontains='Meat'
            ).aggregate(avg=Avg('average_price'))['avg']
            fish_avg = PriceEntry.objects.filter(
                report=r, commodity__category__name__icontains='Fish'
            ).aggregate(avg=Avg('average_price'))['avg']
            price_trend.append({
                'date': r.report_date.strftime('%b %d'),
                'vegetables': round(float(veg_avg), 2) if veg_avg else None,
                'meat': round(float(meat_avg), 2) if meat_avg else None,
                'fish': round(float(fish_avg), 2) if fish_avg else None,
            })

        # System alerts
        alerts = []
        if pending_documents > 0:
            alerts.append({'type': 'warning', 'message': f'{pending_documents} document(s) pending review'})
        overdue_sanitation = Vendor.objects.filter(compliance_rate__lt=70, is_active=True).count()
        if overdue_sanitation > 0:
            alerts.append({'type': 'error', 'message': f'{overdue_sanitation} vendor(s) below 70% compliance'})

        return Response({
            'stats': {
                'total_stalls': total_stalls,
                'occupied_stalls': occupied_stalls,
                'active_vendors': active_vendors,
                'open_complaints': open_complaints,
                'pending_documents': pending_documents,
                'occupancy_rate': round((occupied_stalls / total_stalls * 100), 1) if total_stalls > 0 else 0,
            },
            'section_occupancy': section_data,
            'complaints_by_category': complaint_by_category,
            'recent_complaints': recent_data,
            'price_trend': price_trend,
            'alerts': alerts,
        })


class ReportsView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        section_id = request.query_params.get('section')
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')

        stall_qs = Stall.objects.all()
        complaint_qs = Complaint.objects.all()
        vendor_qs = Vendor.objects.all()

        if section_id:
            stall_qs = stall_qs.filter(section_id=section_id)
            complaint_qs = complaint_qs.filter(stall__section_id=section_id)
            vendor_qs = vendor_qs.filter(stall__section_id=section_id)

        if date_from:
            complaint_qs = complaint_qs.filter(created_at__date__gte=date_from)
        if date_to:
            complaint_qs = complaint_qs.filter(created_at__date__lte=date_to)

        total = stall_qs.count()
        occupied = stall_qs.filter(status='occupied').count()
        vacant = stall_qs.filter(status='vacant').count()
        reserved = stall_qs.filter(status='reserved').count()
        flagged = stall_qs.filter(status='flagged').count()

        sections = MarketSection.objects.annotate(
            total=Count('stalls'),
            occupied=Count('stalls', filter=Q(stalls__status='occupied')),
            vacant=Count('stalls', filter=Q(stalls__status='vacant')),
            reserved=Count('stalls', filter=Q(stalls__status='reserved')),
        ).values('code', 'name', 'total', 'occupied', 'vacant', 'reserved')

        section_report = []
        for s in sections:
            rate = round((s['occupied'] / s['total'] * 100), 1) if s['total'] > 0 else 0
            section_report.append({**s, 'occupancy_rate': rate})

        # Complaint trend (last 6 months)
        complaint_trend = []
        today = date.today()
        for i in range(5, -1, -1):
            month_start = (today.replace(day=1) - timedelta(days=i*28)).replace(day=1)
            month_end = (month_start + timedelta(days=32)).replace(day=1)
            count = Complaint.objects.filter(
                created_at__date__gte=month_start,
                created_at__date__lt=month_end
            ).count()
            complaint_trend.append({
                'month': month_start.strftime('%b %Y'),
                'count': count,
            })

        return Response({
            'occupancy': {
                'total': total,
                'occupied': occupied,
                'vacant': vacant,
                'reserved': reserved,
                'flagged': flagged,
                'rate': round((occupied / total * 100), 1) if total > 0 else 0,
            },
            'section_report': section_report,
            'complaint_trend': complaint_trend,
            'complaint_summary': {
                'total': complaint_qs.count(),
                'open': complaint_qs.filter(status='open').count(),
                'reviewing': complaint_qs.filter(status='reviewing').count(),
                'resolved': complaint_qs.filter(status='resolved').count(),
            },
            'vendor_compliance': {
                'avg_rate': round(float(vendor_qs.aggregate(avg=Avg('compliance_rate'))['avg'] or 0), 1),
                'below_70': vendor_qs.filter(compliance_rate__lt=70).count(),
            }
        })


class PublicStatsView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        total_stalls = Stall.objects.count()
        open_stalls = Stall.objects.filter(status='occupied').count()
        active_vendors = Vendor.objects.filter(is_active=True).count()
        sections = MarketSection.objects.count()

        # Public stall cards
        stalls = Stall.objects.filter(status='occupied').select_related('section', 'vendor').order_by('stall_number')[:12]
        stall_cards = []
        for stall in stalls:
            v = getattr(stall, 'vendor', None)
            stall_cards.append({
                'id': stall.id,
                'stall_number': stall.stall_number,
                'category': stall.category,
                'section': stall.section.name,
                'vendor_name': v.full_name if v else None,
                'products': v.products_list[:4] if v else [],
                'status': stall.status,
            })

        # Public price data (latest report)
        latest_report = PriceReport.objects.filter(is_published=True).order_by('-report_date').first()
        price_categories = []
        if latest_report:
            from apps.prices.models import CommodityCategory
            for cat in CommodityCategory.objects.all()[:4]:
                entries = PriceEntry.objects.filter(
                    report=latest_report,
                    commodity__category=cat
                ).select_related('commodity')[:3]
                price_categories.append({
                    'category': cat.name,
                    'items': [{'name': e.commodity.name, 'price': float(e.average_price or 0), 'unit': e.commodity.unit} for e in entries]
                })

        return Response({
            'stats': {
                'total_stalls': total_stalls,
                'open_stalls': open_stalls,
                'active_vendors': active_vendors,
                'categories': sections,
            },
            'stall_cards': stall_cards,
            'price_categories': price_categories,
        })
