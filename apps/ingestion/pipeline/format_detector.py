"""
Stage 3 — Format Detector

Responsibilities:
  - Determine whether the normalized text matches FORMAT_B, FORMAT_A, or UNKNOWN.
  - Signal the correct SourceDocument status so the pipeline records a precise
    reason for any skip/failure.

Detection rules (derived from Phase 0 PDF audit):

  FORMAT_B  — "PRICE RANGE" AND "PREVAILING" AND "Daily Price Index" present
              → Parser supported in MVP. Proceed to Stage 4.

  FORMAT_A  — "(Average Retail Price)" present
              → Not supported by MVP parser.
              → SourceDocument.status = SKIPPED_UNSUPPORTED_FORMAT

  UNKNOWN   — Neither signature found.
              → SourceDocument.status = FAILED

Note: Detection runs on the full normalized text, not per-page.
The marker strings are stable DA CALABARZON header strings confirmed
across all 16 FORMAT_B PDFs audited in Phase 0.
"""

from __future__ import annotations

from enum import Enum

from .normalizer import NormalizationResult


class DocumentFormat(str, Enum):
    FORMAT_B = "FORMAT_B"   # Daily Price Index — MVP supported
    FORMAT_A = "FORMAT_A"   # Legacy format — not supported in MVP
    UNKNOWN  = "UNKNOWN"    # Unrecognised format


# ---------------------------------------------------------------------------
# Signature strings — confirmed from Phase 0 audit
# ---------------------------------------------------------------------------

# FORMAT_B must have ALL three markers
_FORMAT_B_REQUIRED: list[str] = [
    "PRICE RANGE",
    "PREVAILING",
    "Daily Price Index",
]

# FORMAT_A is identified by ANY of these markers
_FORMAT_A_MARKERS: list[str] = [
    "(Average Retail Price)",
    "Average Retail Price",
]


def detect_format(normalization_result: NormalizationResult) -> DocumentFormat:
    """
    Detect the document format from normalized text.

    Args:
        normalization_result: NormalizationResult from stage 2.

    Returns:
        DocumentFormat enum member.
    """
    text = normalization_result.normalized_text

    # FORMAT_B check — all required markers must be present
    if all(marker in text for marker in _FORMAT_B_REQUIRED):
        return DocumentFormat.FORMAT_B

    # FORMAT_A check — any marker identifies it
    if any(marker in text for marker in _FORMAT_A_MARKERS):
        return DocumentFormat.FORMAT_A

    return DocumentFormat.UNKNOWN
