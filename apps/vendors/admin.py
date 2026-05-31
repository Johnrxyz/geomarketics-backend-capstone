from django.contrib import admin
from .models import MarketSection, Stall, Vendor


@admin.register(MarketSection)
class MarketSectionAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'description']
    search_fields = ['code', 'name']
    ordering = ['code']


@admin.register(Stall)
class StallAdmin(admin.ModelAdmin):
    list_display = ['stall_number', 'section', 'category', 'status', 'area_sqm', 'monthly_rent']
    list_filter = ['section', 'status', 'category']
    search_fields = ['stall_number', 'category']
    ordering = ['stall_number']


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'email', 'phone', 'stall', 'is_active', 'compliance_rate', 'joined_at']
    list_filter = ['is_active', 'stall__section']
    search_fields = ['first_name', 'last_name', 'email', 'stall__stall_number']
    ordering = ['last_name', 'first_name']
    raw_id_fields = ['stall', 'user']
