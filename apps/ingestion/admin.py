from django.contrib import admin
from .models import SourceDocument


@admin.register(SourceDocument)
class SourceDocumentAdmin(admin.ModelAdmin):
    list_display = (
        'source_filename', 'publication_date', 'status',
        'page_count', 'extraction_engine', 'downloaded_at',
    )
    list_filter   = ('status', 'source_type', 'extraction_engine')
    search_fields = ('source_filename', 'source_url', 'error_message')
    readonly_fields = (
        'checksum_sha256', 'downloaded_at', 'processed_at',
        'raw_extracted_text', 'normalized_text',
        'pdf_producer', 'pdf_creator', 'pdf_version',
        'page_count', 'extraction_engine',
    )
    fieldsets = (
        ('Source', {
            'fields': ('source_filename', 'source_url', 'source_type', 'publication_date',
                       'file_path', 'checksum_sha256'),
        }),
        ('Pipeline Status', {
            'fields': ('status', 'error_message', 'downloaded_at', 'processed_at'),
        }),
        ('PDF Metadata', {
            'fields': ('page_count', 'extraction_engine', 'pdf_producer', 'pdf_creator', 'pdf_version'),
            'classes': ('collapse',),
        }),
        ('Extraction Artifacts', {
            'fields': ('raw_extracted_text', 'normalized_text'),
            'classes': ('collapse',),
        }),
    )

    actions = ['reprocess_documents']

    @admin.action(description="Reprocess selected documents")
    def reprocess_documents(self, request, queryset):
        from apps.ingestion.pipeline.orchestrator import run_pipeline
        count = 0
        for doc in queryset:
            run_pipeline(
                file_path=doc.file_path,
                publication_date=doc.publication_date,
                source_filename=doc.source_filename,
                source_url=doc.source_url,
                source_type=doc.source_type,
                force_reprocess=True
            )
            count += 1
        self.message_user(request, f"Successfully reprocessed {count} document(s).")
