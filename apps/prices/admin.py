from django.contrib import admin
from .models import CommodityCategory, Commodity, PriceReport, PriceEntry


@admin.register(CommodityCategory)
class CommodityCategoryAdmin(admin.ModelAdmin):
    list_display = ['roman_numeral', 'name', 'order']
    ordering = ['order']


@admin.register(Commodity)
class CommodityAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'unit', 'standard_price', 'is_active']
    list_filter = ['category', 'unit', 'is_active']
    search_fields = ['name']
    ordering = ['category__order', 'order']


@admin.register(PriceReport)
class PriceReportAdmin(admin.ModelAdmin):
    list_display = ['report_date', 'period_label', 'submitted_by', 'is_published', 'created_at']
    list_filter = ['is_published']
    ordering = ['-report_date']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(PriceEntry)
class PriceEntryAdmin(admin.ModelAdmin):
    list_display = ['report', 'commodity', 'average_price', 'remark']
    list_filter = ['remark', 'commodity__category']
    search_fields = ['commodity__name']
