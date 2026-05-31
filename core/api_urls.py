from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from apps.users.views import UserViewSet, LoginView, LogoutView, MeView
from apps.vendors.views import MarketSectionViewSet, StallViewSet, VendorViewSet
from apps.complaints.views import ComplaintViewSet
from apps.documents.views import DocumentViewSet
from apps.sanitation.views import SanitationSessionViewSet, SanitationRecordViewSet
from apps.prices.views import CommodityCategoryViewSet, CommodityViewSet, PriceReportViewSet
from apps.analytics.views import DashboardView, ReportsView, PublicStatsView
from apps.notifications.views import NotificationViewSet

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'sections', MarketSectionViewSet, basename='section')
router.register(r'stalls', StallViewSet, basename='stall')
router.register(r'vendors', VendorViewSet, basename='vendor')
router.register(r'complaints', ComplaintViewSet, basename='complaint')
router.register(r'documents', DocumentViewSet, basename='document')
router.register(r'sanitation/sessions', SanitationSessionViewSet, basename='sanitation-session')
router.register(r'sanitation/records', SanitationRecordViewSet, basename='sanitation-record')
router.register(r'prices/categories', CommodityCategoryViewSet, basename='commodity-category')
router.register(r'prices/commodities', CommodityViewSet, basename='commodity')
router.register(r'prices/reports', PriceReportViewSet, basename='price-report')
router.register(r'notifications', NotificationViewSet, basename='notification')

urlpatterns = [
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('auth/me/', MeView.as_view(), name='me'),
    path('analytics/dashboard/', DashboardView.as_view(), name='dashboard'),
    path('analytics/reports/', ReportsView.as_view(), name='reports'),
    path('public/stats/', PublicStatsView.as_view(), name='public-stats'),
    path('', include(router.urls)),
]
