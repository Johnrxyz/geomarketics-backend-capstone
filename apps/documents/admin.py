from django.contrib import admin
from .models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['title', 'vendor', 'document_type', 'status', 'expiry_date', 'created_at']
    list_filter = ['status', 'document_type']
    search_fields = ['title', 'vendor__first_name', 'vendor__last_name']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at', 'reviewed_at']
