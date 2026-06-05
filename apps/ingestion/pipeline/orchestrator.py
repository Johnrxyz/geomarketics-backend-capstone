"""
Pipeline Orchestrator

Ties together Stages 1–3 (Extraction → Normalization → Format Detection)
and persists the outcome to SourceDocument.

Does NOT parse price data (Stage 4 / Phase 1C).
After this runs, SourceDocument will be in one of:
  PROCESSED              → FORMAT_B confirmed, ready for parser
  UNSUPPORTED_IMAGE_PDF  → No text layer
  SKIPPED_UNSUPPORTED_FORMAT → FORMAT_A detected
  FAILED                 → Unhandled error or UNKNOWN format

Usage:
  from apps.ingestion.pipeline.orchestrator import run_pipeline
  doc = run_pipeline(file_path, publication_date, source_filename)
"""

from __future__ import annotations

import datetime
import logging
import traceback

from django.utils import timezone

from .exceptions import ExtractionError, ImageOnlyPDFError, UnsupportedFormatError
from .extractor import extract
from .normalizer import normalize
from .format_detector import detect_format, DocumentFormat

logger = logging.getLogger(__name__)


def run_pipeline(
    file_path: str,
    publication_date: datetime.date,
    source_filename: str,
    source_url: str | None = None,
    source_type: str = "da_website",
    force_reprocess: bool = False,
) -> "SourceDocument":
    """
    Run Stages 1–3 of the ingestion pipeline for a single PDF.

    If a SourceDocument with the same checksum already exists and
    force_reprocess=False, returns the existing record without reprocessing.

    Args:
        file_path:        Absolute path to the PDF file on disk.
        publication_date: Date on the DA report (from filename or manual entry).
        source_filename:  Original filename (e.g. "May 18, 2026.pdf").
        source_url:       URL the file was downloaded from (optional).
        source_type:      One of SourceDocument.SOURCE_TYPE_CHOICES values.
        force_reprocess:  If True, re-run even if document was already processed.

    Returns:
        The SourceDocument instance (saved to DB).
    """
    # Import here to keep module importable without Django setup
    from apps.ingestion.models import SourceDocument

    # ── Stage 0: Check for duplicate ──────────────────────────────
    # We hash the file first to detect duplicates before touching the DB.
    import hashlib
    h = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        checksum = h.hexdigest()
    except OSError as exc:
        logger.error("Cannot compute checksum for %s: %s", file_path, exc)
        raise ExtractionError(f"Cannot read file: {exc}") from exc

    existing = SourceDocument.objects.filter(checksum_sha256=checksum).first()
    if existing and not force_reprocess:
        logger.info(
            "Skipping %s — already ingested as SourceDocument pk=%s (status=%s)",
            source_filename, existing.pk, existing.status,
        )
        return existing

    # ── Create / reset SourceDocument ──────────────────────────────
    doc, _ = SourceDocument.objects.update_or_create(
        checksum_sha256=checksum,
        defaults={
            "source_filename":  source_filename,
            "source_url":       source_url,
            "source_type":      source_type,
            "publication_date": publication_date,
            "file_path":        file_path,
            "status":           SourceDocument.STATUS_PROCESSING,
            "error_message":    None,
            "processed_at":     None,
        }
    )

    logger.info("Ingesting: %s (pk=%s)", source_filename, doc.pk)

    try:
        # ── Stage 1: Extraction ────────────────────────────────────
        logger.debug("[%s] Stage 1 — Extracting text with PyPDF", source_filename)
        extraction = extract(file_path)

        raw_text = extraction.raw_text

        # ── Stage 2: Normalization ─────────────────────────────────
        logger.debug("[%s] Stage 2 — Normalizing text", source_filename)
        norm_result = normalize(extraction)

        # ── Stage 3: Format Detection ──────────────────────────────
        logger.debug("[%s] Stage 3 — Detecting format", source_filename)
        doc_format = detect_format(norm_result)
        logger.info("[%s] Detected format: %s", source_filename, doc_format.value)

        # ── Persist extraction artifacts ──────────────────────────
        doc.page_count          = extraction.page_count
        doc.extraction_engine   = "pypdf"
        doc.pdf_producer        = extraction.pdf_producer
        doc.pdf_creator         = extraction.pdf_creator
        doc.pdf_version         = extraction.pdf_version
        doc.raw_extracted_text  = raw_text
        doc.normalized_text     = norm_result.normalized_text

        # ── Set status based on format ─────────────────────────────
        if doc_format == DocumentFormat.FORMAT_B:
            from django.db import transaction
            from apps.prices.models import PriceSnapshot
            from apps.ingestion.pipeline.parser_format_b import parse_format_b
            
            logger.debug("[%s] Stage 4 — Parsing FORMAT_B", source_filename)
            snapshots = parse_format_b(doc)
            
            with transaction.atomic():
                # Idempotency: clear existing snapshots for this document
                deleted, _ = PriceSnapshot.objects.filter(source_document=doc).delete()
                if deleted:
                    logger.info("[%s] Cleared %d existing snapshots", source_filename, deleted)
                
                # Bulk create new snapshots
                if snapshots:
                    PriceSnapshot.objects.bulk_create(snapshots)
                    logger.info("[%s] Saved %d PriceSnapshot records", source_filename, len(snapshots))
                
            doc.status = SourceDocument.STATUS_PROCESSED

        elif doc_format == DocumentFormat.FORMAT_A:
            doc.status = SourceDocument.STATUS_SKIPPED_UNSUPPORTED_FORMAT
            doc.error_message = (
                "FORMAT_A detected (legacy regional summary style). "
                "Not supported by the current MVP parser. "
                "Deferred to Historical Backfill phase."
            )

        else:  # UNKNOWN
            doc.status = SourceDocument.STATUS_FAILED
            doc.error_message = (
                f"UNKNOWN format — none of the FORMAT_B or FORMAT_A "
                f"signatures were found in the normalized text."
            )

    except ImageOnlyPDFError as exc:
        logger.warning("[%s] Image-only PDF: %s", source_filename, exc)
        doc.status = SourceDocument.STATUS_UNSUPPORTED_IMAGE_PDF
        doc.error_message = str(exc)

    except ExtractionError as exc:
        logger.error("[%s] Extraction failed: %s", source_filename, exc)
        doc.status = SourceDocument.STATUS_FAILED
        doc.error_message = str(exc)

    except Exception as exc:  # noqa: BLE001
        tb = traceback.format_exc()
        logger.error("[%s] Unexpected pipeline error:\n%s", source_filename, tb)
        doc.status = SourceDocument.STATUS_FAILED
        doc.error_message = f"{type(exc).__name__}: {exc}\n\n{tb}"

    finally:
        doc.processed_at = timezone.now()
        doc.save()
        logger.info(
            "[%s] Pipeline complete — status: %s (pk=%s)",
            source_filename, doc.status, doc.pk,
        )

    return doc
