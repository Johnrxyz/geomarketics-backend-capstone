from django.contrib import admin
from .models import Complaint


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ['complaint_number', 'subject', 'category', 'status', 'vendor', 'stall', 'created_at']
    list_filter = ['status', 'category']
    search_fields = ['complaint_number', 'subject', 'complainant_name', 'vendor__first_name', 'vendor__last_name']
    ordering = ['-created_at']
    readonly_fields = ['complaint_number', 'created_at', 'updated_at']
