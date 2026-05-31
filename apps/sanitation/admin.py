from django.contrib import admin
from .models import SanitationCheckItem, SanitationSession, SanitationRecord


@admin.register(SanitationCheckItem)
class SanitationCheckItemAdmin(admin.ModelAdmin):
    list_display = ['label', 'name', 'order', 'is_active']
    ordering = ['order']


@admin.register(SanitationSession)
class SanitationSessionAdmin(admin.ModelAdmin):
    list_display = ['date', 'section', 'conducted_by', 'compliance_rate', 'created_at']
    list_filter = ['section', 'date']
    ordering = ['-date']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(SanitationRecord)
class SanitationRecordAdmin(admin.ModelAdmin):
    list_display = ['session', 'vendor', 'check_item', 'status']
    list_filter = ['status', 'check_item']
    search_fields = ['vendor__first_name', 'vendor__last_name']
