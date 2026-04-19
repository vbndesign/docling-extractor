"""Unified extraction service.

Exposes a single async function `extract` that accepts one of three input
shapes and returns an `ExtractionResult`:

1. HTTP(S) URL string pointing at an HTML page
2. HTTP(S) URL string pointing at a PDF
3. Local `pathlib.Path` / path-string OR file-like object containing a PDF

Downstream layers (endpoints, file writer, frontmatter) call `extract` and
never touch Docling directly. `http_client` and `converter` are injected as
keyword-only arguments — they are lifespan-scoped singletons created by the
FastAPI app (Story 1.4).

Exception boundary: this module only raises `DoclingExtractorError` (or
subclasses). Docling/httpx exceptions are translated at the boundary.
"""

from __future__ import annotations

import asyncio
import io
import re
from pathlib import Path
from typing import Any, BinaryIO

import httpx
from curl_cffi.requests import AsyncSession as CurlAsyncSession
from curl_cffi.requests.exceptions import RequestException as CurlRequestException
from docling.datamodel.base_models import DocumentStream
from docling.document_converter import DocumentConverter

from .errors import ConversionError, InvalidInputError, SourceFetchError
from .models import ExtractedMetadata, ExtractionResult, SourceDescriptor, SourceKind

Source = str | Path | BinaryIO
HttpClient = httpx.AsyncClient | CurlAsyncSession

PDF_MAGIC = b"%PDF-"
HTTP_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
HTTP_ACCEPT = (
    "text/html,application/xhtml+xml,application/xml;q=0.9,"
    "application/pdf;q=0.9,*/*;q=0.8"
)
HTTP_ACCEPT_LANGUAGE = "en-US,en;q=0.9"
HTTP_IMPERSONATE = "chrome"

_REQUEST_ERRORS: tuple[type[Exception], ...] = (httpx.RequestError, CurlRequestException)


def make_http_client() -> CurlAsyncSession:
    """Factory for the shared async HTTP client.

    Uses ``curl_cffi`` with TLS impersonation because browser-like headers
    alone are no longer sufficient against Cloudflare's fingerprinting tier
    used by sites like medium.com (httpx's OpenSSL TLS ClientHello is
    flagged as a bot even with a Chrome User-Agent). Impersonating Chrome's
    JA3/JA4 TLS + HTTP/2 fingerprint restores parity with a real browser.

    Timeouts (30 s total / 10 s connect preserved as a single 30 s cap since
    curl_cffi exposes one timeout knob) and the 5-hop redirect cap from
    Story 1.2 AC9 are preserved.
    """

    return CurlAsyncSession(
        impersonate=HTTP_IMPERSONATE,
        headers={
            "User-Agent": HTTP_USER_AGENT,
            "Accept": HTTP_ACCEPT,
            "Accept-Language": HTTP_ACCEPT_LANGUAGE,
        },
        timeout=30,
        allow_redirects=True,
        max_redirects=5,
    )


_TITLE_RE = re.compile(rb"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_META_AUTHOR_RE = re.compile(
    rb"""<meta\b[^>]*\bname\s*=\s*['"]author['"][^>]*\bcontent\s*=\s*['"]([^'"]+)['"]""",
    re.IGNORECASE,
)


def _parse_html_meta(html_bytes: bytes) -> dict[str, str]:
    """Extract <title> and <meta name="author"> from raw HTML.

    Docling focuses on body content; the small top-of-document tags are
    cheaper to parse here with a targeted regex than to traverse the
    produced document tree.
    """

    meta: dict[str, str] = {}
    title_match = _TITLE_RE.search(html_bytes)
    if title_match:
        value = title_match.group(1).decode("utf-8", errors="replace").strip()
        if value:
            meta["source_title"] = value
    author_match = _META_AUTHOR_RE.search(html_bytes)
    if author_match:
        value = author_match.group(1).decode("utf-8", errors="replace").strip()
        if value:
            meta["author"] = value
    return meta


def _run_docling(
    source_for_docling: Any, *, converter: DocumentConverter
) -> tuple[str, dict[str, Any]]:
    """Private wrapper around `DocumentConverter.convert`.

    Isolated so unit tests can monkeypatch it and avoid invoking the real
    (slow) Docling pipeline. Translates any Docling exception into the
    typed `ConversionError`.
    """

    try:
        result = converter.convert(source_for_docling)
        markdown = result.document.export_to_markdown()
    except Exception as exc:  # Docling raises a variety of subclasses
        raise ConversionError(f"Docling conversion failed: {exc}") from exc

    metadata: dict[str, Any] = {}
    doc = getattr(result, "document", None)
    if doc is not None:
        name = getattr(doc, "name", None)
        if isinstance(name, str) and name.strip():
            metadata["source_title"] = name.strip()
    return markdown, metadata


async def _detect_url_kind(url: str, *, http_client: HttpClient) -> SourceKind:
    """Decide whether `url` points at HTML or PDF.

    Prefers a HEAD + Content-Type check; if the origin rejects HEAD (405,
    403, or a transport error) it falls back to a small Range GET and
    sniffs magic bytes.
    """

    head_response: Any = None
    try:
        head_response = await http_client.head(url)
    except _REQUEST_ERRORS:
        head_response = None

    if head_response is not None and head_response.status_code < 400:
        content_type = head_response.headers.get("content-type", "").lower()
        if content_type.startswith("application/pdf"):
            return "url_pdf"
        if content_type.startswith("text/html"):
            return "url_html"

    try:
        range_response = await http_client.get(url, headers={"Range": "bytes=0-1023"})
    except _REQUEST_ERRORS as exc:
        raise SourceFetchError(f"Failed to fetch {url}: {exc}") from exc

    if range_response.status_code >= 400:
        raise SourceFetchError(
            f"Non-success status {range_response.status_code} fetching {url}"
        )

    prefix = range_response.content[:1024]
    if prefix.startswith(PDF_MAGIC):
        return "url_pdf"
    stripped = prefix.lstrip()
    if stripped.startswith(b"<"):
        return "url_html"
    raise InvalidInputError(f"Could not determine content type of {url}")


async def _fetch_bytes(url: str, *, http_client: HttpClient) -> bytes:
    try:
        response = await http_client.get(url)
    except _REQUEST_ERRORS as exc:
        raise SourceFetchError(f"Failed to fetch {url}: {exc}") from exc

    if response.status_code >= 400:
        raise SourceFetchError(
            f"Non-success status {response.status_code} fetching {url}"
        )
    return response.content


def _is_url(value: Any) -> bool:
    return isinstance(value, str) and (
        value.startswith("http://") or value.startswith("https://")
    )


async def extract(
    source: Source,
    *,
    http_client: HttpClient,
    converter: DocumentConverter,
) -> ExtractionResult:
    """Extract Markdown and metadata from any supported source.

    See module docstring for the accepted shapes. Never raises Docling or
    httpx exceptions directly — they are translated into
    `DoclingExtractorError` subclasses.
    """

    if _is_url(source):
        url = source  # type: ignore[assignment]
        kind = await _detect_url_kind(url, http_client=http_client)
        body = await _fetch_bytes(url, http_client=http_client)
        stream_name = "remote.pdf" if kind == "url_pdf" else "remote.html"
        docling_input = DocumentStream(name=stream_name, stream=io.BytesIO(body))
        markdown, meta = await asyncio.to_thread(
            _run_docling, docling_input, converter=converter
        )
        if kind == "url_html":
            for key, value in _parse_html_meta(body).items():
                if value:
                    meta[key] = value
        descriptor = SourceDescriptor(kind=kind, location=url)

    elif hasattr(source, "read"):
        data = source.read()  # type: ignore[union-attr]
        if not isinstance(data, bytes | bytearray):
            raise InvalidInputError("File-like source must yield bytes from .read()")
        if not data.startswith(PDF_MAGIC):
            raise InvalidInputError(
                "Uploaded file is not a valid PDF (missing %PDF- magic bytes)"
            )
        name = getattr(source, "name", None) or "upload.pdf"
        if isinstance(name, str):
            display_name = Path(name).name
        else:
            display_name = "upload.pdf"
        docling_input = DocumentStream(name=display_name, stream=io.BytesIO(bytes(data)))
        markdown, meta = await asyncio.to_thread(
            _run_docling, docling_input, converter=converter
        )
        descriptor = SourceDescriptor(
            kind="pdf_upload",
            location=display_name,
            original_filename=display_name,
        )

    elif isinstance(source, str | Path):
        path = Path(source)
        if not path.exists() or not path.is_file():
            raise InvalidInputError(f"File not found: {path}")
        if path.suffix.lower() != ".pdf":
            raise InvalidInputError(
                f"Only .pdf files are supported for local paths: {path}"
            )
        with path.open("rb") as handle:
            head = handle.read(len(PDF_MAGIC))
        if not head.startswith(PDF_MAGIC):
            raise InvalidInputError(
                f"File is not a valid PDF (missing %PDF- magic bytes): {path}"
            )
        markdown, meta = await asyncio.to_thread(_run_docling, path, converter=converter)
        descriptor = SourceDescriptor(
            kind="pdf_local_path",
            location=str(path.resolve()),
            original_filename=path.name,
        )

    else:
        raise InvalidInputError(
            f"Unsupported source type: {type(source).__name__}"
        )

    year = meta.get("year")
    if isinstance(year, str) and year.isdigit():
        year = int(year)
    elif not isinstance(year, int):
        year = None

    metadata = ExtractedMetadata(
        source_title=meta.get("source_title") or None,
        author=meta.get("author") or None,
        year=year,
    )
    return ExtractionResult(markdown=markdown, metadata=metadata, source=descriptor)
