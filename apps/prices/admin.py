from django.contrib import admin
from .models import (
    CommodityCategory, Commodity, CommodityAlias,
    PriceSnapshot,
)


class CommodityAliasInline(admin.TabularInline):
    model = CommodityAlias
    extra = 1
    fields = ('alias', 'source')


@admin.register(CommodityCategory)
class CommodityCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'order', 'default_unit']
    ordering     = ['order']


@admin.register(Commodity)
class CommodityAdmin(admin.ModelAdmin):
    list_display  = ['name', 'category', 'unit', 'is_active']
    list_filter   = ['category', 'unit', 'is_active']
    search_fields = ['name']
    ordering      = ['category__order', 'order']
    inlines       = [CommodityAliasInline]


@admin.register(CommodityAlias)
class CommodityAliasAdmin(admin.ModelAdmin):
    list_display  = ('alias', 'commodity', 'source', 'created_at')
    list_filter   = ('source',)
    search_fields = ('alias', 'commodity__name')


@admin.register(PriceSnapshot)
class PriceSnapshotAdmin(admin.ModelAdmin):
    list_display  = ('survey_date', 'market', 'commodity', 'price_min', 'price_max', 'average_price', 'prevailing_price', 'data_quality')
    list_filter   = ('survey_date', 'data_quality', 'market', 'commodity__category')
    search_fields = ('market__name', 'commodity__name')
    readonly_fields = ('created_at', 'source_document')
    date_hierarchy = 'survey_date'



