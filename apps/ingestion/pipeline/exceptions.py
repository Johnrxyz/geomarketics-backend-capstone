"""
Pipeline exceptions.
All pipeline-specific errors inherit from PipelineError so callers can
catch the whole family with a single except clause.
"""


class PipelineError(Exception):
    """Base class for all pipeline errors."""


class ExtractionError(PipelineError):
    """Raised when PyPDF cannot open or read the file."""


class NormalizationError(PipelineError):
    """Raised when the normalization layer encounters an unexpected state."""


class UnsupportedFormatError(PipelineError):
    """
    Raised when the format detector determines the document is not FORMAT_B.
    Carry the detected format label so callers can set the correct status.
    """

    def __init__(self, message: str, detected_format: str):
        super().__init__(message)
        self.detected_format = detected_format


class ImageOnlyPDFError(PipelineError):
    """Raised when no extractable text is found — image-only PDF."""
