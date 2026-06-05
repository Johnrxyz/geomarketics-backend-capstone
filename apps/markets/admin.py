from django.contrib import admin
from .models import Market, MarketAlias, UnknownEntity


class MarketAliasInline(admin.TabularInline):
    model = MarketAlias
    extra = 1
    fields = ('alias', 'source')


@admin.register(Market)
class MarketAdmin(admin.ModelAdmin):
    list_display  = ('name', 'province', 'city_municipality', 'market_type', 'is_active')
    list_filter   = ('province', 'market_type', 'is_active')
    search_fields = ('name', 'city_municipality')
    inlines       = [MarketAliasInline]
    ordering      = ('province', 'name')


@admin.register(MarketAlias)
class MarketAliasAdmin(admin.ModelAdmin):
    list_display  = ('alias', 'market', 'source', 'created_at')
    list_filter   = ('source',)
    search_fields = ('alias', 'market__name')


@admin.register(UnknownEntity)
class UnknownEntityAdmin(admin.ModelAdmin):
    list_display  = ('raw_name', 'entity_type', 'resolution_status', 'occurrence_count', 'last_seen')
    list_filter   = ('entity_type', 'resolution_status')
    search_fields = ('raw_name',)
    readonly_fields = ('first_seen', 'last_seen', 'occurrence_count', 'source_document')
    fieldsets = (
        ('Entity', {
            'fields': ('entity_type', 'raw_name', 'source_document', 'occurrence_count', 'first_seen', 'last_seen')
        }),
        ('Resolution', {
            'fields': ('resolution_status', 'resolved_to_market', 'resolved_to_commodity'),
            'description': (
                'Map this raw name to an existing Market or Commodity, then set status to Resolved. '
                'After saving, re-run the parse command on the associated SourceDocument.'
            ),
        }),
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.resolution_status == 'resolved':
            if obj.entity_type == 'market' and obj.resolved_to_market:
                MarketAlias.objects.get_or_create(
                    market=obj.resolved_to_market,
                    alias=obj.raw_name,
                    defaults={'source': 'manual_resolution'}
                )
            elif obj.entity_type == 'commodity' and obj.resolved_to_commodity:
                from apps.prices.models import CommodityAlias
                CommodityAlias.objects.get_or_create(
                    commodity=obj.resolved_to_commodity,
                    alias=obj.raw_name,
                    defaults={'source': 'manual_resolution'}
                )
