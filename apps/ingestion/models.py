from django.db import models


class SourceDocument(models.Model):
    """
    System of record for every DA CALABARZON PDF downloaded.
    Preserved permanently; used as FK for all PriceSnapshots.
    Supports reprocessing when parsers are improved.
    """

    # ── Source type ──────────────────────────────────────────────
    SOURCE_DA_WEBSITE    = 'da_website'
    SOURCE_MANUAL_UPLOAD = 'manual_upload'
    SOURCE_TYPE_CHOICES  = [
        (SOURCE_DA_WEBSITE,    'DA CALABARZON Website'),
        (SOURCE_MANUAL_UPLOAD, 'Manual Upload'),
    ]

    # ── Pipeline status ──────────────────────────────────────────
    STATUS_PENDING                   = 'PENDING'
    STATUS_PROCESSING                = 'PROCESSING'
    STATUS_PROCESSED                 = 'PROCESSED'
    STATUS_FAILED                    = 'FAILED'
    STATUS_UNSUPPORTED_IMAGE_PDF     = 'UNSUPPORTED_IMAGE_PDF'
    STATUS_SKIPPED_UNSUPPORTED_FORMAT = 'SKIPPED_UNSUPPORTED_FORMAT'
    STATUS_CHOICES = [
        (STATUS_PENDING,                    'Pending — not yet processed'),
        (STATUS_PROCESSING,                 'Processing — pipeline running'),
        (STATUS_PROCESSED,                  'Processed — snapshots written'),
        (STATUS_FAILED,                     'Failed — unhandled error'),
        (STATUS_UNSUPPORTED_IMAGE_PDF,      'Unsupported — image-only PDF, no text layer'),
        (STATUS_SKIPPED_UNSUPPORTED_FORMAT, 'Skipped — text extracted but format not supported by current parser (e.g. FORMAT_A)'),
    ]

    # ── Core fields ───────────────────────────────────────────────
    source_filename  = models.CharField(max_length=255)
    source_url       = models.TextField(blank=True, null=True)
    source_type      = models.CharField(max_length=50, choices=SOURCE_TYPE_CHOICES, default=SOURCE_DA_WEBSITE)
    publication_date = models.DateField(db_index=True)
    file_path        = models.TextField()
    checksum_sha256  = models.CharField(max_length=64, unique=True)

    # ── Pipeline status ───────────────────────────────────────────
    status           = models.CharField(max_length=50, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)

    # ── PDF metadata (nullable — captured when available) ─────────
    page_count       = models.PositiveIntegerField(null=True, blank=True)
    extraction_engine = models.CharField(max_length=50, default='pypdf', blank=True)
    pdf_producer     = models.CharField(max_length=255, null=True, blank=True,
                                        help_text='PDF producer software, e.g. Skia/PDF, iLovePDF')
    pdf_creator      = models.CharField(max_length=255, null=True, blank=True,
                                        help_text='PDF creator application')
    pdf_version      = models.CharField(max_length=20, null=True, blank=True,
                                        help_text='PDF specification version, e.g. 1.4, 1.7')

    # ── Extraction artifacts ──────────────────────────────────────
    raw_extracted_text  = models.TextField(null=True, blank=True,
                                           help_text='Raw text as returned by PyPDF before normalization')
    normalized_text     = models.TextField(null=True, blank=True,
                                           help_text='Text after normalization layer; used by parser')

    # ── Error tracking ────────────────────────────────────────────
    error_message    = models.TextField(null=True, blank=True)

    # ── Timestamps ───────────────────────────────────────────────
    downloaded_at    = models.DateTimeField(auto_now_add=True)
    processed_at     = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-publication_date']
        indexes = [
            models.Index(fields=['-publication_date'], name='idx_srcdoc_pub_date'),
            models.Index(fields=['status'],            name='idx_srcdoc_status'),
        ]

    def __str__(self):
        return f'{self.source_filename} [{self.status}]'

    @property
    def is_processable(self):
        """True if the document can be sent to the parser."""
        return self.status == self.STATUS_PENDING
