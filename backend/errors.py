"""Typed exception hierarchy + FastAPI handlers for the docling extractor.

The service layer never raises generic `Exception` nor framework-specific
`HTTPException`. It raises `DoclingExtractorError` subclasses carrying a
stable `code` (for the error catalog) and an `http_status` hint consumed by
the global FastAPI handler defined below.

Story 1.4 adds: `UploadTooLargeError`, `RequestTimeoutError`, the shared
`ERROR_CATALOG`, and the content-negotiation-aware handlers that translate
domain exceptions into JSON or HTML responses (arch §10.2, §10.3).
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

logger = logging.getLogger("docling_extractor.errors")


class DoclingExtractorError(Exception):
    """Base class for every error raised by the extractor service layer."""

    code: str = "INTERNAL_ERROR"
    http_status: int = 500


class InvalidInputError(DoclingExtractorError):
    code = "INVALID_INPUT"
    http_status = 400


class UploadTooLargeError(DoclingExtractorError):
    code = "UPLOAD_TOO_LARGE"
    http_status = 413


class SourceFetchError(DoclingExtractorError):
    code = "SOURCE_FETCH_FAILED"
    http_status = 502


class ConversionError(DoclingExtractorError):
    code = "CONVERSION_FAILED"
    http_status = 422


class RequestTimeoutError(DoclingExtractorError):
    code = "REQUEST_TIMEOUT"
    http_status = 504


ERROR_CATALOG: dict[str, tuple[str, str]] = {
    "INVALID_INPUT": (
        "Invalid request payload.",
        "Provide exactly one of: url, file, or local_path.",
    ),
    "UPLOAD_TOO_LARGE": (
        "Upload exceeds size limit.",
        "Reduce file size or adjust MAX_UPLOAD_MB in .env.",
    ),
    "SOURCE_FETCH_FAILED": (
        "Failed to fetch source.",
        "Verify the URL is publicly accessible and returns HTTP 200.",
    ),
    "CONVERSION_FAILED": (
        "Docling conversion failed.",
        "Source may be corrupted, empty, or a scanned PDF (OCR not supported in v1).",
    ),
    "REQUEST_TIMEOUT": (
        "Extraction exceeded timeout.",
        "Try a smaller source or increase REQUEST_TIMEOUT_SECONDS in .env.",
    ),
    "INTERNAL_ERROR": (
        "An unexpected error occurred.",
        "Check the server console logs for details.",
    ),
}


def prefers_html(request: Request) -> bool:
    """Return True when the client explicitly prefers HTML over JSON.

    Precedence (arch §7.3):
    * Explicit ``Accept: application/json`` always wins → JSON (preserves the
      PRD contract for CLI/script clients, even if HX-Request is set).
    * ``Accept`` containing ``text/html`` → HTML.
    * ``HX-Request: true`` without an explicit JSON Accept → HTML. HTMX does
      not set ``Accept: text/html`` on XHR (browser default is ``*/*``), so
      the ``HX-Request`` header is the reliable signal that the caller wants
      the server-rendered partial rather than the JSON envelope.
    * Otherwise → JSON.
    """

    accept = request.headers.get("accept", "")
    if "application/json" in accept:
        return False
    if "text/html" in accept:
        return True
    return request.headers.get("hx-request", "").lower() == "true"


def _resolve_payload(exc: DoclingExtractorError) -> dict[str, str]:
    default_msg, hint = ERROR_CATALOG.get(exc.code, ERROR_CATALOG["INTERNAL_ERROR"])
    message = str(exc) if str(exc) else default_msg
    return {"code": exc.code, "message": message, "hint": hint}


async def handler(request: Request, exc: DoclingExtractorError) -> Response:
    payload = _resolve_payload(exc)

    if prefers_html(request):
        templates = request.app.state.templates
        return templates.TemplateResponse(
            request,
            "partials/result_error.html",
            payload,
            status_code=exc.http_status,
        )
    return JSONResponse(
        status_code=exc.http_status,
        content={"status": "error", **payload},
    )


async def unexpected_handler(request: Request, exc: Exception) -> Response:
    # Catch-all: promote any untyped exception to INTERNAL_ERROR.
    # Detailed logging stays here; the client receives the generic envelope.
    logger.exception("Unhandled exception during request", exc_info=exc)
    promoted = DoclingExtractorError()
    promoted.code = "INTERNAL_ERROR"
    promoted.http_status = 500
    return await handler(request, promoted)


def register_handlers(app: FastAPI) -> None:
    """Attach the typed + catch-all handlers to a FastAPI application."""

    app.add_exception_handler(DoclingExtractorError, handler)
    app.add_exception_handler(Exception, unexpected_handler)
