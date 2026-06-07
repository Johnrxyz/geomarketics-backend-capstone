from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from .models import Market, MarketAlias, UnknownEntity
from .serializers import MarketSerializer, MarketAliasSerializer, UnknownEntitySerializer

class IsAdminOrPublic(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_authenticated and request.user.role == 'admin'

class MarketViewSet(viewsets.ModelViewSet):
    queryset = Market.objects.all()
    serializer_class = MarketSerializer
    permission_classes = [IsAdminOrPublic]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['province', 'market_type', 'is_active']
    search_fields = ['name', 'city_municipality']
    ordering_fields = ['province', 'name']

class MarketAliasViewSet(viewsets.ModelViewSet):
    queryset = MarketAlias.objects.select_related('market').all()
    serializer_class = MarketAliasSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['market', 'source']
    search_fields = ['alias', 'market__name']

class UnknownEntityViewSet(viewsets.ModelViewSet):
    queryset = UnknownEntity.objects.select_related('resolved_to_market', 'resolved_to_commodity', 'source_document').all()
    serializer_class = UnknownEntitySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['entity_type', 'resolution_status', 'source_document']
    search_fields = ['raw_name']
    ordering_fields = ['last_seen', 'first_seen', 'occurrence_count']

    @action(detail=True, methods=['post'], url_path='resolve')
    def resolve(self, request, pk=None):
        entity = self.get_object()
        resolution_status = request.data.get('resolution_status')
        resolved_to_market_id = request.data.get('resolved_to_market')
        resolved_to_commodity_id = request.data.get('resolved_to_commodity')

        if resolution_status:
            entity.resolution_status = resolution_status
        if resolved_to_market_id:
            entity.resolved_to_market_id = resolved_to_market_id
        if resolved_to_commodity_id:
            entity.resolved_to_commodity_id = resolved_to_commodity_id

        entity.save()
        return Response(self.get_serializer(entity).data)
