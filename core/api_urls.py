from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from apps.users.views import UserViewSet, LoginView, LogoutView, MeView
from apps.vendors.views import MarketSectionViewSet, StallViewSet, VendorViewSet
from apps.complaints.views import ComplaintViewSet, BlotterViewSet
from apps.documents.views import DocumentViewSet
from apps.sanitation.views import SanitationSessionViewSet, SanitationRecordViewSet
from apps.prices.views import CommodityCategoryViewSet, CommodityViewSet, PriceSnapshotViewSet
from apps.analytics.views import DashboardView, ReportsView, PublicStatsView, AIRiskProfileViewSet, AccomplishmentReportViewSet
from apps.violations.views import ViolationViewSet, PenaltyViewSet
from apps.notifications.views import NotificationViewSet
from apps.markets.views import MarketViewSet, MarketAliasViewSet, UnknownEntityViewSet

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'sections', MarketSectionViewSet, basename='section')
router.register(r'stalls', StallViewSet, basename='stall')
router.register(r'vendors', VendorViewSet, basename='vendor')
router.register(r'complaints', ComplaintViewSet, basename='complaint')
router.register(r'blotters', BlotterViewSet, basename='blotter')
router.register(r'documents', DocumentViewSet, basename='document')
router.register(r'sanitation/sessions', SanitationSessionViewSet, basename='sanitation-session')
router.register(r'sanitation/records', SanitationRecordViewSet, basename='sanitation-record')
router.register(r'prices/categories', CommodityCategoryViewSet, basename='commodity-category')
router.register(r'prices/commodities', CommodityViewSet, basename='commodity')

router.register(r'prices/snapshots', PriceSnapshotViewSet, basename='price-snapshot')
router.register(r'notifications', NotificationViewSet, basename='notification')
router.register(r'markets', MarketViewSet, basename='market')
router.register(r'markets-aliases', MarketAliasViewSet, basename='market-alias')
router.register(r'unknown-entities', UnknownEntityViewSet, basename='unknown-entity')
router.register(r'violations', ViolationViewSet, basename='violation')
router.register(r'penalties', PenaltyViewSet, basename='penalty')
router.register(r'ai-risk', AIRiskProfileViewSet, basename='ai-risk')
router.register(r'accomplishment-reports', AccomplishmentReportViewSet, basename='accomplishment-report')

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
