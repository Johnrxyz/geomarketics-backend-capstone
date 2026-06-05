"""
Stage 1 — PDF Extraction

Responsibilities:
  - Open the PDF with PyPDF
  - Extract per-page raw text
  - Capture PDF metadata (producer, creator, pdf_version)
  - Detect image-only PDFs (no text layer across all pages)
  - Return a structured ExtractionResult

Deliberately simple: NO interpretation, NO normalization here.
The raw text is preserved as-is for auditability.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from typing import Optional

import pypdf

from .exceptions import ExtractionError, ImageOnlyPDFError


@dataclass
class PageExtraction:
    """Text extracted from a single PDF page."""
    page_number: int          # 1-indexed
    raw_text: str | None      # None means image-only page
    is_empty: bool = False    # True when PyPDF returns empty string

    @property
    def has_text(self) -> bool:
        return bool(self.raw_text and self.raw_text.strip())


@dataclass
class ExtractionResult:
    """
    Everything extracted from a single PDF file.
    Passed to the Normalizer for stage 2 processing.
    """
    file_path: str
    checksum_sha256: str
    page_count: int
    pages: list[PageExtraction] = field(default_factory=list)

    # PDF metadata — all optional (depends on producer)
    pdf_producer: str | None = None
    pdf_creator: str | None = None
    pdf_version: str | None = None

    @property
    def raw_text(self) -> str:
        """
        Full raw text: all pages joined with a page separator.
        Empty pages emit a placeholder so page boundaries are preserved.
        """
        parts = []
        for p in self.pages:
            parts.append(f"<<<PAGE {p.page_number}>>>")
            parts.append(p.raw_text or "<<<IMAGE PAGE>>>")
        return "\n".join(parts)

    @property
    def has_any_text(self) -> bool:
        return any(p.has_text for p in self.pages)

    @property
    def text_page_count(self) -> int:
        return sum(1 for p in self.pages if p.has_text)


def _sha256(file_path: str) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _get_meta(reader: pypdf.PdfReader, key: str) -> str | None:
    """Safely pull a value from PdfReader.metadata, return None if absent."""
    try:
        meta = reader.metadata
        if meta is None:
            return None
        val = meta.get(key)
        return str(val).strip() if val else None
    except Exception:
        return None


def extract(file_path: str) -> ExtractionResult:
    """
    Extract text and metadata from a PDF file.

    Args:
        file_path: Absolute path to the PDF.

    Returns:
        ExtractionResult

    Raises:
        ExtractionError: If the file cannot be read or PyPDF raises.
        ImageOnlyPDFError: If no text is found on any page.
    """
    if not os.path.isfile(file_path):
        raise ExtractionError(f"File not found: {file_path}")

    try:
        checksum = _sha256(file_path)
    except OSError as exc:
        raise ExtractionError(f"Cannot read file for checksum: {exc}") from exc

    try:
        reader = pypdf.PdfReader(file_path)
    except Exception as exc:
        raise ExtractionError(f"PyPDF failed to open file: {exc}") from exc

    page_count = len(reader.pages)

    # PDF metadata
    pdf_version  = getattr(reader, 'pdf_version', None)
    if pdf_version:
        pdf_version = str(pdf_version)
    pdf_producer = _get_meta(reader, "/Producer")
    pdf_creator  = _get_meta(reader, "/Creator")

    pages: list[PageExtraction] = []
    for idx, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text()
        except Exception:
            text = None

        pages.append(PageExtraction(
            page_number=idx,
            raw_text=text if text else None,
            is_empty=not bool(text),
        ))

    result = ExtractionResult(
        file_path=file_path,
        checksum_sha256=checksum,
        page_count=page_count,
        pages=pages,
        pdf_producer=pdf_producer,
        pdf_creator=pdf_creator,
        pdf_version=pdf_version,
    )

    if not result.has_any_text:
        raise ImageOnlyPDFError(
            f"No extractable text found in {os.path.basename(file_path)}. "
            f"All {page_count} pages appear to be image-only."
        )

    return result
