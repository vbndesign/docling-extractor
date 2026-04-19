"""Typed exception hierarchy for the docling extractor.

The service layer never raises generic `Exception` nor framework-specific
`HTTPException`. It raises `DoclingExtractorError` subclasses carrying a
stable `code` (for the error catalog) and an `http_status` hint consumed by
the FastAPI exception handler (Story 1.4).

Story 1.2 scope: base class + `InvalidInputError`, `SourceFetchError`,
`ConversionError`. `UploadTooLargeError`, `RequestTimeoutError`, and the
`ERROR_CATALOG` are introduced in Story 1.4.
"""

from __future__ import annotations


class DoclingExtractorError(Exception):
    """Base class for every error raised by the extractor service layer."""

    code: str = "INTERNAL_ERROR"
    http_status: int = 500


class InvalidInputError(DoclingExtractorError):
    code = "INVALID_INPUT"
    http_status = 400


class SourceFetchError(DoclingExtractorError):
    code = "SOURCE_FETCH_FAILED"
    http_status = 502


class ConversionError(DoclingExtractorError):
    code = "CONVERSION_FAILED"
    http_status = 422
