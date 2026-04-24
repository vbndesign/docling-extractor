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

Story 1.7 — Chunked extraction: PDFs with more than
``settings.pdf_chunk_threshold`` pages are split into blocks of
``settings.pdf_chunk_size`` pages before being passed to Docling, then the
per-chunk markdowns are concatenated. This works around a native-memory
accumulation in Docling's pypdfium2 preprocess stage that otherwise
silently drops ~90% of large-PDF pages (`PARTIAL_SUCCESS` returned with
only a handful of converted pages). Chunks reuse the singleton
``DocumentConverter`` (R2); only the PDF heap is re-initialized per
``convert()`` call, which is what actually bounds the leak.
"""

from __future__ import annotations

import asyncio
import io
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any, BinaryIO

import httpx
import pypdfium2 as pdfium
from curl_cffi.requests import AsyncSession as CurlAsyncSession
from curl_cffi.requests.exceptions import RequestException as CurlRequestException
from docling.datamodel.base_models import DocumentStream
from docling.document_converter import DocumentConverter

from .config import Settings, get_settings
from .errors import ConversionError, InvalidInputError, SourceFetchError
from .models import ExtractedMetadata, ExtractionResult, SourceDescriptor, SourceKind

Source = str | Path | BinaryIO
HttpClient = httpx.AsyncClient | CurlAsyncSession

PDF_MAGIC = b"%PDF-"
# DOCX files are OOXML packages — ZIP archives whose local file header
# starts with ``PK\x03\x04``. Story 1.8 AC3: we only sniff the first 4
# bytes and defer OOXML-vs-xlsx/pptx discrimination to Docling itself
# (its backend raises ``ConversionError`` when it can't open a package).
DOCX_MAGIC = b"PK\x03\x04"

_DOCX_CORE_XML_PATH = "docProps/core.xml"
_DOCX_CORE_NS = {
    "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcterms": "http://purl.org/dc/terms/",
}

# Minimum stripped markdown length below which we treat the conversion as
# "produced no usable content". The real failure mode is a scanned PDF (no
# OCR) or a JS-rendered SPA — Docling yields a page-shell with zero text
# runs, which stringifies to a few whitespace/heading chars. 10 is a small
# non-zero threshold: it rejects empty/whitespace output without false-
# positiving real short docs (a 1-line note still exceeds it).
_MIN_MARKDOWN_CHARS = 10
HTTP_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
HTTP_ACCEPT = (
    "text/html,application/xhtml+xml,application/xml;q=0.9," "application/pdf;q=0.9,*/*;q=0.8"
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


def _parse_docx_core_properties(data: bytes) -> dict[str, Any]:
    """Read ``docProps/core.xml`` from a DOCX archive and map to FR4 keys.

    Story 1.8 AC5. Returns a dict with any subset of ``source_title``,
    ``author``, ``year`` — absent or blank values are simply omitted
    (PRD FR4: omission over placeholders). Never raises for malformed or
    missing metadata; Docling's own pipeline surfaces the real failure if
    the package is truly unreadable.
    """

    meta: dict[str, Any] = {}
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            with zf.open(_DOCX_CORE_XML_PATH) as handle:
                xml_bytes = handle.read()
    except (KeyError, zipfile.BadZipFile):
        return meta

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return meta

    title_el = root.find("dc:title", _DOCX_CORE_NS)
    if title_el is not None and title_el.text:
        title = title_el.text.strip()
        if title:
            meta["source_title"] = title

    creator_el = root.find("dc:creator", _DOCX_CORE_NS)
    if creator_el is not None and creator_el.text:
        # dc:creator can list multiple authors separated by ``;`` — take
        # the first to match the ExtractedMetadata shape (single string).
        first = creator_el.text.split(";")[0].strip()
        if first:
            meta["author"] = first

    created_el = root.find("dcterms:created", _DOCX_CORE_NS)
    if created_el is not None and created_el.text:
        raw = created_el.text.strip()
        # ISO-8601 timestamps start with YYYY (e.g. 2024-03-15T12:34:56Z).
        if len(raw) >= 4 and raw[:4].isdigit():
            meta["year"] = int(raw[:4])

    return meta


async def _convert_docx_bytes(
    data: bytes,
    *,
    display_name: str,
    converter: DocumentConverter,
) -> tuple[str, dict[str, Any]]:
    """Run Docling over a DOCX byte stream (single call, no chunking).

    DOCX has no OCR or pypdfium2 heap pressure, so the Story 1.7 chunker
    is intentionally bypassed. Metadata is read from ``docProps/core.xml``
    directly — Docling's ``document.name`` for DOCX mirrors the stream
    name (i.e. the filename), which is not a useful ``source_title``.
    """

    docling_input = DocumentStream(name=display_name, stream=io.BytesIO(data))
    markdown, _docling_meta, _ = await asyncio.to_thread(
        _run_docling, docling_input, converter=converter
    )
    return markdown, _parse_docx_core_properties(data)


def _chunk_pdf_bytes(data: bytes, chunk_size: int) -> list[bytes]:
    """Split a PDF byte stream into a list of self-contained PDF chunks.

    Each returned item is a full, valid PDF with up to ``chunk_size`` pages
    (the last chunk may be smaller). Order is preserved: concatenating the
    chunks' pages reproduces the original document.

    Story 1.7 rationale: the Docling pipeline accumulates native memory
    inside the pypdfium2 preprocess stage within a single
    ``DocumentConverter.convert()`` call. Isolating ~10 pages per call
    keeps that heap bounded and converts 100+ page PDFs losslessly, where
    a single-shot conversion silently loses the bulk of pages.
    """

    if chunk_size <= 0:
        raise InvalidInputError(f"pdf_chunk_size must be positive, got {chunk_size}")

    src = pdfium.PdfDocument(io.BytesIO(data))
    try:
        n = len(src)
        out: list[bytes] = []
        for start in range(0, n, chunk_size):
            end = min(start + chunk_size, n)
            dst = pdfium.PdfDocument.new()
            try:
                # import_pages uses 0-based indices (see pypdfium2 docs);
                # off-by-one here silently drops the first page of each chunk.
                dst.import_pages(src, list(range(start, end)))
                buf = io.BytesIO()
                dst.save(buf)
                out.append(buf.getvalue())
            finally:
                dst.close()
        return out
    finally:
        src.close()


def _pdf_page_count(data: bytes) -> int:
    """Return the PDF's page count without holding the handle.

    We need the number before deciding single-call vs chunked path; the
    handle is closed right after to keep the pypdfium2 heap small for
    the real conversion call.
    """

    doc = pdfium.PdfDocument(io.BytesIO(data))
    try:
        return len(doc)
    finally:
        doc.close()


def _collect_failed_pages(result: Any) -> list[int]:
    """Pull 1-based page numbers from Docling's ``result.errors`` list.

    Docling exposes per-error ``page_no`` for preprocess/layout failures;
    we filter out entries that don't name a page (e.g. pipeline-level
    errors) because those are already reflected in ``status != SUCCESS``.
    Docling itself emits ``page_no`` as 1-based — we preserve that contract
    and the caller applies a chunk offset to translate to document-wide
    page numbers.
    """

    errors = getattr(result, "errors", None) or []
    pages: list[int] = []
    for err in errors:
        page_no = getattr(err, "page_no", None)
        if isinstance(page_no, int) and page_no > 0:
            pages.append(page_no)
    return sorted(set(pages))


def _run_docling(
    source_for_docling: Any, *, converter: DocumentConverter
) -> tuple[str, dict[str, Any], list[int]]:
    """Private wrapper around `DocumentConverter.convert`.

    Isolated so unit tests can monkeypatch it and avoid invoking the real
    (slow) Docling pipeline. Translates any Docling exception into the
    typed `ConversionError`. We pass ``raises_on_error=False`` so that a
    non-SUCCESS status surfaces Docling's own error list in the message
    (the default ``raises_on_error=True`` throws a generic "Input document
    X is not valid" that hides the real cause).

    Returns ``(markdown, metadata, failed_pages)`` where ``failed_pages``
    is a sorted list of 1-based page numbers Docling flagged as failing
    within THIS call (i.e. relative to the chunk, not the full document).
    The caller is responsible for applying a page offset when aggregating
    across chunks.

    On hard failure (``FAILURE`` status AND no ``PARTIAL_SUCCESS`` markdown
    to salvage) we still raise ``ConversionError`` — a chunk that produced
    zero output has nothing useful to contribute to the aggregate.
    """

    try:
        result = converter.convert(source_for_docling, raises_on_error=False)
    except Exception as exc:  # Transport / unexpected failures only
        raise ConversionError(f"Docling conversion failed: {exc}") from exc

    status = getattr(result, "status", None)
    status_name = getattr(status, "name", str(status))
    if status_name not in {"SUCCESS", "PARTIAL_SUCCESS"}:
        errors = getattr(result, "errors", None) or []
        error_details = (
            "; ".join(getattr(e, "error_message", None) or str(e) for e in errors) or "no details"
        )
        raise ConversionError(f"Docling conversion status={status_name}: {error_details}")

    try:
        markdown = result.document.export_to_markdown()
    except Exception as exc:
        raise ConversionError(f"Docling markdown export failed: {exc}") from exc

    metadata: dict[str, Any] = {}
    doc = getattr(result, "document", None)
    if doc is not None:
        name = getattr(doc, "name", None)
        if isinstance(name, str) and name.strip():
            metadata["source_title"] = name.strip()

    failed_pages = _collect_failed_pages(result) if status_name == "PARTIAL_SUCCESS" else []
    return markdown, metadata, failed_pages


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
        raise SourceFetchError(f"Non-success status {range_response.status_code} fetching {url}")

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
        raise SourceFetchError(f"Non-success status {response.status_code} fetching {url}")
    return response.content


def _is_url(value: Any) -> bool:
    return isinstance(value, str) and (value.startswith("http://") or value.startswith("https://"))


def _guard_non_empty_markdown(markdown: str, kind: SourceKind) -> None:
    """Raise `ConversionError` with a kind-specific hint if markdown is empty.

    Story 1.6 AC2: a scanned PDF (no extractable text) or a JS-rendered SPA
    would otherwise produce a `.md` with only frontmatter and an empty body.
    The error message steers the user to the real cause (no OCR / no JS /
    empty DOCX) rather than letting them chase a silent success.
    """

    if len(markdown.strip()) >= _MIN_MARKDOWN_CHARS:
        return
    if kind == "url_html":
        raise ConversionError(
            "Extracted content is empty. "
            "JavaScript-rendered pages (SPA) are not supported in v1."
        )
    if kind in ("docx_upload", "docx_local_path"):
        raise ConversionError("DOCX produced no extractable text (file may be empty or corrupt).")
    raise ConversionError(
        "PDF appears to be scanned without extractable text. " "OCR is not enabled in v1."
    )


async def _convert_pdf_bytes(
    data: bytes,
    *,
    display_name: str,
    converter: DocumentConverter,
    settings: Settings,
) -> tuple[str, dict[str, Any], int, list[int]]:
    """Run Docling over a PDF byte stream, chunking when needed.

    Returns ``(markdown, metadata, total_pages, failed_pages)`` where
    ``markdown`` is either the direct single-call output (small PDFs) or
    the ``"\\n\\n"``-joined concatenation of per-chunk markdowns in original
    page order. ``failed_pages`` contains 1-based page numbers relative to
    the full document (chunk offsets applied). ``metadata`` is taken from
    the first chunk that produced non-empty metadata, since author/title
    are almost always at the start of the document.

    Raises ``ConversionError`` when:
    * zero chunks produced usable markdown (aggregate guard for the empty
      output case already enforced per-chunk by Docling's own status check),
    * the fraction of failed pages exceeds
      ``settings.max_failed_pages_ratio`` (the caller turns this into an
      HTTP 422 via the error catalog).
    """

    total_pages = _pdf_page_count(data)

    if total_pages <= settings.pdf_chunk_threshold:
        docling_input = DocumentStream(name=display_name, stream=io.BytesIO(data))
        markdown, meta, failed_pages = await asyncio.to_thread(
            _run_docling, docling_input, converter=converter
        )
        return markdown, meta, total_pages, failed_pages

    chunks = _chunk_pdf_bytes(data, settings.pdf_chunk_size)
    chunk_markdowns: list[str] = []
    aggregated_meta: dict[str, Any] = {}
    aggregated_failed: list[int] = []

    for idx, chunk_bytes in enumerate(chunks):
        offset = idx * settings.pdf_chunk_size
        # Distinct per-chunk stream name so Docling logs are diagnosable,
        # while still rooting them under the source file's basename.
        chunk_name = f"{display_name}#chunk{idx + 1:03d}"
        docling_input = DocumentStream(name=chunk_name, stream=io.BytesIO(chunk_bytes))
        chunk_md, chunk_meta, chunk_failed = await asyncio.to_thread(
            _run_docling, docling_input, converter=converter
        )
        if chunk_md.strip():
            chunk_markdowns.append(chunk_md)
        if not aggregated_meta and chunk_meta:
            aggregated_meta = chunk_meta
        aggregated_failed.extend(offset + page_no for page_no in chunk_failed)

    if not chunk_markdowns:
        raise ConversionError(
            f"Conversion produced no markdown across {len(chunks)} chunks "
            f"({total_pages} pages total)."
        )

    ratio = len(aggregated_failed) / total_pages if total_pages else 0.0
    if ratio > settings.max_failed_pages_ratio:
        raise ConversionError(
            f"Conversion failed for {len(aggregated_failed)} of {total_pages} pages "
            f"(over threshold {settings.max_failed_pages_ratio:.2f})."
        )

    # Plain "\n\n" separator — do NOT inject HTML comments or chunk
    # headers; the frontmatter at the top of the file is the single place
    # where partial/failed metadata lives (arch §5.2).
    full_markdown = "\n\n".join(chunk_markdowns)
    return full_markdown, aggregated_meta, total_pages, sorted(set(aggregated_failed))


async def extract(
    source: Source,
    *,
    http_client: HttpClient,
    converter: DocumentConverter,
    settings: Settings | None = None,
) -> ExtractionResult:
    """Extract Markdown and metadata from any supported source.

    See module docstring for the accepted shapes. Never raises Docling or
    httpx exceptions directly — they are translated into
    `DoclingExtractorError` subclasses.

    ``settings`` is an optional keyword argument for test injection; when
    omitted we read the process-wide settings via ``get_settings()``. The
    HTTP-fetch path only reads chunk/threshold values, so callers can
    safely pass a synthetic ``Settings`` scoped to their test.
    """

    if settings is None:
        settings = get_settings()

    if _is_url(source):
        url = source  # type: ignore[assignment]
        kind = await _detect_url_kind(url, http_client=http_client)
        body = await _fetch_bytes(url, http_client=http_client)
        if kind == "url_pdf":
            markdown, meta, total_pages, failed_pages = await _convert_pdf_bytes(
                body,
                display_name="remote.pdf",
                converter=converter,
                settings=settings,
            )
        else:
            docling_input = DocumentStream(name="remote.html", stream=io.BytesIO(body))
            markdown, meta, failed_pages = await asyncio.to_thread(
                _run_docling, docling_input, converter=converter
            )
            total_pages = None
            for key, value in _parse_html_meta(body).items():
                if value:
                    meta[key] = value
        descriptor = SourceDescriptor(kind=kind, location=url)

    elif hasattr(source, "read"):
        data = source.read()  # type: ignore[union-attr]
        if not isinstance(data, bytes | bytearray):
            raise InvalidInputError("File-like source must yield bytes from .read()")
        raw_name = getattr(source, "name", None)
        name: str = raw_name if isinstance(raw_name, str) and raw_name else "upload.pdf"
        display_name = Path(name).name
        data_bytes = bytes(data)
        suffix = Path(name).suffix.lower()

        # Story 1.8 AC3a: when the caller declares a ``.docx`` extension,
        # the content MUST actually be a ZIP/OOXML package. A PDF renamed
        # to ``.docx`` is a malformed request — we reject it with the
        # DOCX-specific hint instead of silently transcoding it as a PDF.
        if suffix == ".docx":
            if not data_bytes.startswith(DOCX_MAGIC):
                raise InvalidInputError(
                    "Uploaded file is not a valid .docx (missing ZIP magic bytes)"
                )
            markdown, meta = await _convert_docx_bytes(
                data_bytes,
                display_name=display_name,
                converter=converter,
            )
            total_pages = None
            failed_pages = []
            descriptor = SourceDescriptor(
                kind="docx_upload",
                location=display_name,
                original_filename=display_name,
            )
        elif data_bytes.startswith(PDF_MAGIC):
            markdown, meta, total_pages, failed_pages = await _convert_pdf_bytes(
                data_bytes,
                display_name=display_name,
                converter=converter,
                settings=settings,
            )
            descriptor = SourceDescriptor(
                kind="pdf_upload",
                location=display_name,
                original_filename=display_name,
            )
        elif data_bytes.startswith(DOCX_MAGIC):
            # Unknown/no extension but DOCX magic — accept and route to DOCX.
            markdown, meta = await _convert_docx_bytes(
                data_bytes,
                display_name=display_name,
                converter=converter,
            )
            total_pages = None
            failed_pages = []
            descriptor = SourceDescriptor(
                kind="docx_upload",
                location=display_name,
                original_filename=display_name,
            )
        else:
            raise InvalidInputError(
                "Uploaded file is not a valid PDF or DOCX (missing magic bytes)"
            )

    elif isinstance(source, str | Path):
        path = Path(source)
        if not path.exists() or not path.is_file():
            raise InvalidInputError(f"File not found: {path}")
        suffix = path.suffix.lower()
        if suffix not in {".pdf", ".docx"}:
            raise InvalidInputError(
                f"Only .pdf and .docx files are supported for local paths: {path}"
            )
        data = path.read_bytes()

        if suffix == ".pdf":
            if not data.startswith(PDF_MAGIC):
                raise InvalidInputError(
                    f"File is not a valid PDF (missing %PDF- magic bytes): {path}"
                )
            # Wrap in DocumentStream rather than passing the Path directly:
            # OneDrive reparse points (and some other special filesystems)
            # can break Docling's path-based backends with
            # "Inconsistent number of pages: N!=-1", while the in-memory
            # stream path is unaffected. This also unifies the Docling
            # input shape across URL / upload / local_path branches.
            markdown, meta, total_pages, failed_pages = await _convert_pdf_bytes(
                data,
                display_name=path.name,
                converter=converter,
                settings=settings,
            )
            descriptor = SourceDescriptor(
                kind="pdf_local_path",
                location=str(path.resolve()),
                original_filename=path.name,
            )
        else:  # .docx
            if not data.startswith(DOCX_MAGIC):
                raise InvalidInputError(
                    f"File is not a valid .docx (missing ZIP magic bytes): {path}"
                )
            markdown, meta = await _convert_docx_bytes(
                data,
                display_name=path.name,
                converter=converter,
            )
            total_pages = None
            failed_pages = []
            descriptor = SourceDescriptor(
                kind="docx_local_path",
                location=str(path.resolve()),
                original_filename=path.name,
            )

    else:
        raise InvalidInputError(f"Unsupported source type: {type(source).__name__}")

    _guard_non_empty_markdown(markdown, descriptor.kind)

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
    return ExtractionResult(
        markdown=markdown,
        metadata=metadata,
        source=descriptor,
        partial=bool(failed_pages),
        failed_pages=tuple(failed_pages),
        total_pages=total_pages,
    )
