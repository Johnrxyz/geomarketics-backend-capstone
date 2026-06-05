"""
Stage 2 — Text Normalization Layer

Responsibilities:
  - Collapse duplicated column headers produced by PyPDF layout extraction
  - Normalize whitespace inside known multi-word anchors
  - Remove decorative symbols (◆, ●) if present
  - Strip trailing whitespace per line
  - Collapse excessive blank lines

IMPORTANT:
  - This layer operates on raw_text from the Extractor.
  - The parser MUST consume normalized_text, never raw_text.
  - raw_text is kept in SourceDocument.raw_extracted_text for auditability only.
  - The normalizer must NOT interpret or discard data — only clean formatting artifacts.

Rules are derived from Phase 0 audit observations on the actual PyPDF output.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .extractor import ExtractionResult


# ---------------------------------------------------------------------------
# Known column header tokens that PyPDF sometimes duplicates
# (observed pattern: "BRANDBRAND", "CAVITECAVITE", etc.)
# ---------------------------------------------------------------------------
_DOUBLED_TOKENS: list[str] = [
    "COMMODITY",
    "PRICE RANGE",
    "AVERAGE",
    "PREVAILING",
    "BRAND",
    "CAVITE",
    "LAGUNA",
    "BATANGAS",
    "RIZAL",
    "QUEZON",
    "CALABARZON",
]

# ---------------------------------------------------------------------------
# Multi-word anchors where PyPDF may insert extra whitespace
# ---------------------------------------------------------------------------
_WHITESPACE_FIXES: list[tuple[str, str]] = [
    # Pattern                       → Canonical form
    (r'PRICE\s+RANGE',              'PRICE RANGE'),
    (r'PREVAILING\s+PRICE',         'PREVAILING PRICE'),
    (r'AVERAGE\s+PRICE',            'AVERAGE PRICE'),
    (r'BANTAY\s+PRESYO',            'BANTAY PRESYO'),
    (r'Daily\s+Price\s+Index',      'Daily Price Index'),
    (r'CALABAR\s*ZON',              'CALABARZON'),
    (r'Region\s+IV\s*[-–]\s*A',     'Region IV-A'),
]

# Decorative symbols to remove
_DECORATIVE_RE = re.compile(r'[◆●►▶•]')


@dataclass
class NormalizationResult:
    """Output of the normalization stage."""
    normalized_text: str
    page_count: int
    text_pages_normalized: int

    # Pass-through from ExtractionResult for pipeline chaining
    file_path: str
    checksum_sha256: str
    pdf_producer: str | None
    pdf_creator: str | None
    pdf_version: str | None


def _collapse_doubled_tokens(text: str) -> str:
    """
    Remove exact token repetitions that PyPDF produces when column headers
    span multiple text fragments.
    e.g. "BRANDBRAND" → "BRAND", "CAVITECAVITE" → "CAVITE"
    """
    for token in _DOUBLED_TOKENS:
        # Simple string doubling (no space)
        text = text.replace(token + token, token)
    return text


def _fix_whitespace_anchors(text: str) -> str:
    """Standardize multi-word anchors that may have irregular spacing."""
    for pattern, replacement in _WHITESPACE_FIXES:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def _remove_decorative_symbols(text: str) -> str:
    """Strip decorative symbols used as visual section markers in some PDFs."""
    return _DECORATIVE_RE.sub('', text)


def _normalize_lines(text: str) -> str:
    """
    Per-line cleanup:
      - Strip trailing whitespace from every line
      - Collapse runs of 3+ blank lines to a single blank line
    """
    lines = text.split('\n')
    cleaned: list[str] = []
    blank_count = 0
    for line in lines:
        stripped = line.rstrip()
        if not stripped:
            blank_count += 1
            if blank_count <= 1:
                cleaned.append('')
        else:
            blank_count = 0
            cleaned.append(stripped)
    return '\n'.join(cleaned)


def normalize_page(raw_text: str) -> str:
    """
    Apply the full normalization pipeline to a single page's raw text.
    Called per-page so page boundaries are preserved.
    """
    text = raw_text
    text = _collapse_doubled_tokens(text)
    text = _fix_whitespace_anchors(text)
    text = _remove_decorative_symbols(text)
    text = _normalize_lines(text)
    return text


def normalize(extraction: ExtractionResult) -> NormalizationResult:
    """
    Normalize an ExtractionResult into a single clean text document.

    Page boundaries are preserved using <<<PAGE N>>> markers (same format
    as the extractor) so the parser can still locate page-level context.

    Args:
        extraction: The ExtractionResult from stage 1.

    Returns:
        NormalizationResult with the joined normalized text.
    """
    normalized_parts: list[str] = []
    text_pages_normalized = 0

    for page in extraction.pages:
        normalized_parts.append(f"<<<PAGE {page.page_number}>>>")
        if page.has_text:
            normalized_parts.append(normalize_page(page.raw_text))
            text_pages_normalized += 1
        else:
            normalized_parts.append("<<<IMAGE PAGE>>>")

    normalized_text = "\n".join(normalized_parts)

    return NormalizationResult(
        normalized_text=normalized_text,
        page_count=extraction.page_count,
        text_pages_normalized=text_pages_normalized,
        file_path=extraction.file_path,
        checksum_sha256=extraction.checksum_sha256,
        pdf_producer=extraction.pdf_producer,
        pdf_creator=extraction.pdf_creator,
        pdf_version=extraction.pdf_version,
    )
