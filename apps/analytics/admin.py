from django.contrib import admin
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'action', 'entity_type', 'entity_id', 'created_at']
    list_filter = ['action', 'entity_type']
    search_fields = ['user__username', 'description']
    ordering = ['-created_at']
    readonly_fields = ['created_at']
