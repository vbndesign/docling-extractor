"""Unit tests for `backend.docling_service`.

All tests mock `_run_docling` to keep the suite fast and offline. Real
Docling invocation is deferred to the optional smoke test in
`tests/test_docling_smoke.py` (Story 1.6 territory), not this file.
"""

from __future__ import annotations

import io
from pathlib import Path

import httpx
import pypdfium2 as pdfium
import pytest

from backend import docling_service
from backend.docling_service import (
    HTTP_IMPERSONATE,
    HTTP_USER_AGENT,
    _chunk_pdf_bytes,
    extract,
    make_http_client,
)
from backend.errors import ConversionError, InvalidInputError, SourceFetchError
from backend.models import ExtractionResult

# ---- Helpers ---------------------------------------------------------------


def _patch_run_docling(
    monkeypatch: pytest.MonkeyPatch,
    markdown: str,
    metadata: dict,
    failed_pages: list[int] | None = None,
):
    """Monkeypatch ``_run_docling`` to return the Story 1.7 3-tuple shape."""

    pages = list(failed_pages or [])

    def _stub(_source, *, converter):  # noqa: ARG001 — signature match
        return markdown, dict(metadata), list(pages)

    monkeypatch.setattr(docling_service, "_run_docling", _stub)


# ---- Happy-path tests ------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_html_url_success(
    make_test_http_client, sample_html_bytes, dummy_converter, monkeypatch
):
    _patch_run_docling(
        monkeypatch,
        markdown="# Body extracted by Docling\n",
        metadata={},
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "HEAD":
            return httpx.Response(200, headers={"Content-Type": "text/html; charset=utf-8"})
        return httpx.Response(
            200,
            headers={"Content-Type": "text/html; charset=utf-8"},
            content=sample_html_bytes,
        )

    async with make_test_http_client(handler) as client:
        result = await extract(
            "https://example.com/article",
            http_client=client,
            converter=dummy_converter,
        )

    assert isinstance(result, ExtractionResult)
    assert result.source.kind == "url_html"
    assert result.source.location == "https://example.com/article"
    assert result.markdown == "# Body extracted by Docling\n"
    # HTML metadata should come from raw <title>/<meta> parsing, not Docling
    assert result.metadata.source_title == "Sample Article Title"
    assert result.metadata.author == "Jane Doe"


@pytest.mark.asyncio
async def test_extract_pdf_url_success(
    make_test_http_client, sample_pdf_bytes, dummy_converter, monkeypatch
):
    _patch_run_docling(
        monkeypatch,
        markdown="# PDF body\n",
        metadata={"source_title": "From Docling"},
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "HEAD":
            return httpx.Response(200, headers={"Content-Type": "application/pdf"})
        return httpx.Response(
            200, headers={"Content-Type": "application/pdf"}, content=sample_pdf_bytes
        )

    async with make_test_http_client(handler) as client:
        result = await extract(
            "https://example.com/paper.pdf",
            http_client=client,
            converter=dummy_converter,
        )

    assert result.source.kind == "url_pdf"
    assert result.source.location == "https://example.com/paper.pdf"
    assert result.markdown == "# PDF body\n"
    assert result.metadata.source_title == "From Docling"


@pytest.mark.asyncio
async def test_extract_local_pdf_success(
    make_test_http_client, sample_pdf_path: Path, dummy_converter, monkeypatch
):
    _patch_run_docling(
        monkeypatch,
        markdown="# Local PDF\n",
        metadata={"source_title": "Local Sample"},
    )

    # http_client should not be touched for local paths, but instantiate one anyway
    async with make_test_http_client(lambda r: httpx.Response(500)) as client:
        result = await extract(
            sample_pdf_path,
            http_client=client,
            converter=dummy_converter,
        )

    assert result.source.kind == "pdf_local_path"
    assert result.source.original_filename == sample_pdf_path.name
    assert Path(result.source.location).name == sample_pdf_path.name
    assert result.markdown == "# Local PDF\n"
    assert result.metadata.source_title == "Local Sample"


@pytest.mark.asyncio
async def test_extract_pdf_upload_success(
    make_test_http_client, sample_pdf_bytes, dummy_converter, monkeypatch
):
    _patch_run_docling(
        monkeypatch,
        markdown="# Uploaded\n",
        metadata={},
    )

    upload = io.BytesIO(sample_pdf_bytes)
    upload.name = "my-upload.pdf"  # type: ignore[attr-defined]

    async with make_test_http_client(lambda r: httpx.Response(500)) as client:
        result = await extract(upload, http_client=client, converter=dummy_converter)

    assert result.source.kind == "pdf_upload"
    assert result.source.original_filename == "my-upload.pdf"
    assert result.markdown == "# Uploaded\n"


# ---- Fallback & failure paths ---------------------------------------------


@pytest.mark.asyncio
async def test_extract_head_fallback_to_magic_bytes(
    make_test_http_client, sample_pdf_bytes, dummy_converter, monkeypatch
):
    _patch_run_docling(
        monkeypatch,
        markdown="# PDF via fallback\n",
        metadata={},
    )

    call_log: list[tuple[str, dict[str, str]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        call_log.append((request.method, dict(request.headers)))
        if request.method == "HEAD":
            return httpx.Response(405)  # HEAD not allowed
        if request.headers.get("range"):
            return httpx.Response(
                206,
                headers={"Content-Type": "application/octet-stream"},
                content=sample_pdf_bytes[:1024],
            )
        return httpx.Response(
            200,
            headers={"Content-Type": "application/octet-stream"},
            content=sample_pdf_bytes,
        )

    async with make_test_http_client(handler) as client:
        result = await extract(
            "https://example.com/unknown",
            http_client=client,
            converter=dummy_converter,
        )

    methods = [m for m, _ in call_log]
    assert methods[0] == "HEAD"
    assert methods[1] == "GET"
    # First GET must carry a Range header for magic-byte sniffing
    assert "range" in {k.lower() for k in call_log[1][1]}
    assert result.source.kind == "url_pdf"


@pytest.mark.asyncio
async def test_extract_corrupted_pdf_raises_conversion_error(
    make_test_http_client, sample_pdf_path, dummy_converter, monkeypatch
):
    def _boom(_source, *, converter):  # noqa: ARG001
        raise ConversionError("Docling failed: malformed PDF")

    # Patch both _run_docling (HTML path) and _pdf_page_count (PDF path uses
    # the chunker probe to decide single-vs-chunked before calling Docling).
    monkeypatch.setattr(docling_service, "_run_docling", _boom)

    async with make_test_http_client(lambda r: httpx.Response(500)) as client:
        with pytest.raises(ConversionError):
            await extract(sample_pdf_path, http_client=client, converter=dummy_converter)


@pytest.mark.asyncio
async def test_extract_unreachable_url_raises_source_fetch_error(
    make_test_http_client, dummy_converter, monkeypatch
):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("DNS lookup failed", request=request)

    async with make_test_http_client(handler) as client:
        with pytest.raises(SourceFetchError):
            await extract(
                "https://does-not-resolve.invalid/page",
                http_client=client,
                converter=dummy_converter,
            )


@pytest.mark.asyncio
async def test_extract_unsupported_local_file_raises_invalid_input(
    tmp_path, make_test_http_client, dummy_converter
):
    junk = tmp_path / "file.txt"
    junk.write_text("not a pdf")

    async with make_test_http_client(lambda r: httpx.Response(500)) as client:
        with pytest.raises(InvalidInputError):
            await extract(junk, http_client=client, converter=dummy_converter)


@pytest.mark.asyncio
async def test_extract_pdf_upload_without_magic_raises_invalid_input(
    make_test_http_client, dummy_converter
):
    upload = io.BytesIO(b"not actually a pdf, no magic header")

    async with make_test_http_client(lambda r: httpx.Response(500)) as client:
        with pytest.raises(InvalidInputError):
            await extract(upload, http_client=client, converter=dummy_converter)


# ---- Advisory AC5 check (from @po review) ---------------------------------


@pytest.mark.asyncio
async def test_extract_html_result_contains_no_image_markup(
    make_test_http_client, dummy_converter, monkeypatch
):
    """AC5 advisory: Markdown body must not contain image syntax.

    The service returns whatever Docling produces — the mock emits a
    typical markdown body with no `![...]` nor `<img>`, proving that the
    pipeline does not inject images on its own.
    """

    _patch_run_docling(
        monkeypatch,
        markdown="# Title\n\nParagraph one.\n\nParagraph two with [link](https://x).\n",
        metadata={},
    )

    html_with_image = (
        b"<html><head><title>Has Image</title></head>"
        b"<body><h1>Has Image</h1><p>text</p>"
        b"<img src='x.png' alt='ignored'></body></html>"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "HEAD":
            return httpx.Response(200, headers={"Content-Type": "text/html"})
        return httpx.Response(200, headers={"Content-Type": "text/html"}, content=html_with_image)

    async with make_test_http_client(handler) as client:
        result = await extract(
            "https://example.com/has-image",
            http_client=client,
            converter=dummy_converter,
        )

    assert "![" not in result.markdown
    assert "<img" not in result.markdown.lower()


# ---- HTTP client config (AC9) ---------------------------------------------


def test_make_http_client_uses_documented_config():
    """AC9 (revised again): curl_cffi session with TLS impersonation + headers.

    Earlier iterations relied on browser-like UA alone, which bypassed
    Cloudflare tier 1 (e.g. nngroup.com) but not tier 2 JA3/JA4 TLS
    fingerprinting (e.g. medium.com returned 403). The client now uses
    `curl_cffi` with `impersonate="chrome"` so the TLS ClientHello matches
    Chrome's fingerprint, while still exposing the same documented headers
    for debuggability.
    """

    from curl_cffi.requests import AsyncSession as CurlAsyncSession

    client = make_http_client()
    try:
        assert isinstance(client, CurlAsyncSession)
        ua = client.headers.get("user-agent")
        assert ua is not None
        assert ua.startswith("Mozilla/5.0")
        assert "Chrome/" in ua
        accept = client.headers.get("accept")
        assert accept is not None
        assert "text/html" in accept
        assert "application/pdf" in accept
        assert client.headers.get("accept-language", "").startswith("en")
        # curl_cffi stores timeout as a plain number and the impersonate name
        # as an attribute; both matter for the AC9 contract.
        assert client.timeout == 30
        assert client.impersonate == HTTP_IMPERSONATE
        assert client.allow_redirects is True
        assert client.max_redirects == 5
    finally:
        # AsyncSession.close() is async; the constructor merely allocated state.
        pass


# ---- Story 1.7 — Chunked PDF extraction -----------------------------------


def _build_synthetic_pdf(num_pages: int) -> bytes:
    """Generate a tiny in-memory PDF with `num_pages` text-only pages.

    Uses reportlab (a dev-only dep) so chunker tests remain self-contained
    and do NOT commit yet another fixture PDF. The content is irrelevant;
    only the page count matters for AC7a/AC7e.
    """

    from reportlab.lib.pagesizes import LETTER
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    c.setFont("Helvetica", 10)
    for page_idx in range(num_pages):
        c.drawString(72, 720, f"synthetic page {page_idx + 1} of {num_pages}")
        c.showPage()
    c.save()
    return buf.getvalue()


def _pdf_pages(data: bytes) -> int:
    doc = pdfium.PdfDocument(io.BytesIO(data))
    try:
        return len(doc)
    finally:
        doc.close()


def test_chunk_pdf_splits_into_expected_sizes():
    """AC7a — 25-page PDF chunked at 10 yields 3 sub-PDFs with 10, 10, 5 pages.

    Uses reportlab to synthesize the source PDF in-memory (not committed);
    each chunk is reopened via pypdfium2 to verify its own page count and
    that the sum equals the original (no pages dropped or duplicated).
    """

    data = _build_synthetic_pdf(25)
    chunks = _chunk_pdf_bytes(data, 10)

    assert len(chunks) == 3
    page_counts = [_pdf_pages(chunk) for chunk in chunks]
    assert page_counts == [10, 10, 5]
    assert sum(page_counts) == 25


def test_chunk_pdf_exact_multiple_splits_evenly():
    """Edge: when total is a clean multiple of chunk_size, no short tail chunk."""

    data = _build_synthetic_pdf(20)
    chunks = _chunk_pdf_bytes(data, 10)

    assert len(chunks) == 2
    assert [_pdf_pages(c) for c in chunks] == [10, 10]


def test_chunk_pdf_rejects_non_positive_chunk_size():
    data = _build_synthetic_pdf(5)
    with pytest.raises(InvalidInputError):
        _chunk_pdf_bytes(data, 0)


@pytest.mark.asyncio
async def test_small_pdf_bypasses_chunking(
    tmp_path, make_test_http_client, dummy_converter, monkeypatch
):
    """AC7e — PDFs with pages <= pdf_chunk_threshold skip the chunker entirely.

    Monkeypatches `_chunk_pdf_bytes` with a spy and asserts it was never
    invoked for a 5-page PDF against the default threshold of 20. The spy
    also raises if called, so a regression that routes small PDFs through
    chunking would fail loudly, not silently.
    """

    from backend.config import Settings

    _patch_run_docling(monkeypatch, markdown="# Small\n\nBody.\n", metadata={})

    call_count = 0

    def spy_chunker(data: bytes, chunk_size: int):  # noqa: ARG001
        nonlocal call_count
        call_count += 1
        raise AssertionError("chunker must not be invoked for small PDFs")

    monkeypatch.setattr(docling_service, "_chunk_pdf_bytes", spy_chunker)

    pdf_bytes = _build_synthetic_pdf(5)
    pdf_path = tmp_path / "small.pdf"
    pdf_path.write_bytes(pdf_bytes)

    settings = Settings(
        output_dir=tmp_path,
        max_upload_mb=10,
        request_timeout_seconds=5,
        pdf_chunk_size=10,
        pdf_chunk_threshold=20,
        max_failed_pages_ratio=0.10,
    )

    async with make_test_http_client(lambda r: httpx.Response(500)) as client:
        result = await extract(
            pdf_path,
            http_client=client,
            converter=dummy_converter,
            settings=settings,
        )

    assert call_count == 0
    assert result.partial is False
    assert result.failed_pages == ()
    assert result.total_pages == 5


@pytest.mark.asyncio
async def test_large_pdf_routes_through_chunker(
    tmp_path, make_test_http_client, dummy_converter, monkeypatch
):
    """Complement of AC7e — crossing the threshold MUST trigger chunking.

    Uses a 25-page PDF with threshold=20, chunk_size=10 → 3 chunks, so
    `_run_docling` is called 3 times (once per chunk) and the aggregated
    markdown concatenates the 3 stubbed outputs in order.
    """

    from backend.config import Settings

    call_log: list[str] = []

    def stub(source_for_docling, *, converter):  # noqa: ARG001
        call_log.append(source_for_docling.name)
        idx = len(call_log)
        return f"### chunk {idx}", {}, []

    monkeypatch.setattr(docling_service, "_run_docling", stub)

    pdf_bytes = _build_synthetic_pdf(25)
    pdf_path = tmp_path / "big.pdf"
    pdf_path.write_bytes(pdf_bytes)

    settings = Settings(
        output_dir=tmp_path,
        max_upload_mb=10,
        request_timeout_seconds=5,
        pdf_chunk_size=10,
        pdf_chunk_threshold=20,
        max_failed_pages_ratio=0.10,
    )

    async with make_test_http_client(lambda r: httpx.Response(500)) as client:
        result = await extract(
            pdf_path,
            http_client=client,
            converter=dummy_converter,
            settings=settings,
        )

    assert len(call_log) == 3
    assert all("#chunk" in name for name in call_log)
    assert result.markdown == "### chunk 1\n\n### chunk 2\n\n### chunk 3"
    assert result.total_pages == 25
    assert result.partial is False


@pytest.mark.asyncio
async def test_large_pdf_aggregates_failed_pages_with_chunk_offset(
    tmp_path, make_test_http_client, dummy_converter, monkeypatch
):
    """AC3a — failed page numbers are offset by chunk index.

    Docling reports `page_no` relative to the CHUNK it received (1-based).
    The service must translate to document-wide numbers. Here chunk 2
    reports pages 3 and 4 as failed — globally those are pages 13 and 14.
    Below 10% threshold (2/30 ≈ 6.7%), so response is partial=true, 200 OK.
    """

    from backend.config import Settings

    def stub(source_for_docling, *, converter):  # noqa: ARG001
        name = source_for_docling.name
        failed = [3, 4] if "#chunk002" in name else []
        return "# content", {}, failed

    monkeypatch.setattr(docling_service, "_run_docling", stub)

    pdf_bytes = _build_synthetic_pdf(30)
    pdf_path = tmp_path / "partial.pdf"
    pdf_path.write_bytes(pdf_bytes)

    settings = Settings(
        output_dir=tmp_path,
        max_upload_mb=10,
        request_timeout_seconds=5,
        pdf_chunk_size=10,
        pdf_chunk_threshold=20,
        max_failed_pages_ratio=0.10,
    )

    async with make_test_http_client(lambda r: httpx.Response(500)) as client:
        result = await extract(
            pdf_path,
            http_client=client,
            converter=dummy_converter,
            settings=settings,
        )

    assert result.partial is True
    assert result.failed_pages == (13, 14)
    assert result.total_pages == 30


@pytest.mark.asyncio
async def test_large_pdf_rejects_when_failure_ratio_exceeded(
    tmp_path, make_test_http_client, dummy_converter, monkeypatch
):
    """AC3b — when >MAX_FAILED_PAGES_RATIO pages fail, raise ConversionError."""

    from backend.config import Settings

    def stub(source_for_docling, *, converter):  # noqa: ARG001
        # Every chunk fails its first 5 pages → 15/30 = 50% failure rate.
        return "# content", {}, [1, 2, 3, 4, 5]

    monkeypatch.setattr(docling_service, "_run_docling", stub)

    pdf_bytes = _build_synthetic_pdf(30)
    pdf_path = tmp_path / "burned.pdf"
    pdf_path.write_bytes(pdf_bytes)

    settings = Settings(
        output_dir=tmp_path,
        max_upload_mb=10,
        request_timeout_seconds=5,
        pdf_chunk_size=10,
        pdf_chunk_threshold=20,
        max_failed_pages_ratio=0.10,
    )

    async with make_test_http_client(lambda r: httpx.Response(500)) as client:
        with pytest.raises(ConversionError) as excinfo:
            await extract(
                pdf_path,
                http_client=client,
                converter=dummy_converter,
                settings=settings,
            )

    assert "over threshold" in str(excinfo.value)


@pytest.mark.asyncio
async def test_http_client_sends_user_agent(make_test_http_client, dummy_converter, monkeypatch):
    """AC9 via MockTransport: UA + Accept headers reach the server."""

    _patch_run_docling(
        monkeypatch,
        markdown="# Title\n\nBody paragraph extracted by the mock.\n",
        metadata={},
    )

    seen_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.update({k.lower(): v for k, v in request.headers.items()})
        if request.method == "HEAD":
            return httpx.Response(200, headers={"Content-Type": "text/html"})
        return httpx.Response(
            200,
            headers={"Content-Type": "text/html"},
            content=b"<html><head><title>t</title></head><body>b</body></html>",
        )

    async with make_test_http_client(handler) as client:
        await extract(
            "https://example.com/page",
            http_client=client,
            converter=dummy_converter,
        )

    assert seen_headers.get("user-agent") == HTTP_USER_AGENT
    assert "text/html" in seen_headers.get("accept", "")
    assert seen_headers.get("accept-language", "").startswith("en")
