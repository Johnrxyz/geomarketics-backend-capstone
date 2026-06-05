from django.contrib import admin
from .models import (
    CommodityCategory, Commodity, CommodityAlias,
    PriceSnapshot, PriceReport, PriceEntry,
)


class CommodityAliasInline(admin.TabularInline):
    model = CommodityAlias
    extra = 1
    fields = ('alias', 'source')


@admin.register(CommodityCategory)
class CommodityCategoryAdmin(admin.ModelAdmin):
    list_display = ['roman_numeral', 'name', 'order', 'default_unit']
    ordering     = ['order']


@admin.register(Commodity)
class CommodityAdmin(admin.ModelAdmin):
    list_display  = ['name', 'category', 'unit', 'standard_price', 'is_active']
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


@admin.register(PriceReport)
class PriceReportAdmin(admin.ModelAdmin):
    list_display  = ['report_date', 'period_label', 'submitted_by', 'is_published', 'created_at']
    list_filter   = ['is_published']
    ordering      = ['-report_date']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(PriceEntry)
class PriceEntryAdmin(admin.ModelAdmin):
    list_display  = ['report', 'commodity', 'average_price', 'remark']
    list_filter   = ['remark', 'commodity__category']
    search_fields = ['commodity__name']
