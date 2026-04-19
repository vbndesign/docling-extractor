"""Unit tests for `backend.docling_service`.

All tests mock `_run_docling` to keep the suite fast and offline. Real
Docling invocation is deferred to the optional smoke test in
`tests/test_docling_smoke.py` (Story 1.6 territory), not this file.
"""

from __future__ import annotations

import io
from pathlib import Path

import httpx
import pytest

from backend import docling_service
from backend.docling_service import HTTP_USER_AGENT, extract, make_http_client
from backend.errors import ConversionError, InvalidInputError, SourceFetchError
from backend.models import ExtractionResult

# ---- Helpers ---------------------------------------------------------------


def _patch_run_docling(monkeypatch: pytest.MonkeyPatch, markdown: str, metadata: dict):
    def _stub(_source, *, converter):  # noqa: ARG001 — signature match
        return markdown, dict(metadata)

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
        result = await extract(
            upload, http_client=client, converter=dummy_converter
        )

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

    monkeypatch.setattr(docling_service, "_run_docling", _boom)

    async with make_test_http_client(lambda r: httpx.Response(500)) as client:
        with pytest.raises(ConversionError):
            await extract(
                sample_pdf_path, http_client=client, converter=dummy_converter
            )


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
        return httpx.Response(
            200, headers={"Content-Type": "text/html"}, content=html_with_image
        )

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
    """AC9 (revised): browser-like UA + Accept headers, timeouts, redirect cap.

    The UA is a Chrome string (not the original `docling-extractor/1.0`
    token) because Cloudflare-fronted publishers (e.g. nngroup.com) reject
    bare-token UAs with 403. See module docstring in docling_service.py.
    """

    client = make_http_client()
    try:
        ua = client.headers.get("user-agent")
        assert ua is not None
        assert ua.startswith("Mozilla/5.0")
        assert "Chrome/" in ua
        accept = client.headers.get("accept")
        assert accept is not None
        assert "text/html" in accept
        assert "application/pdf" in accept
        assert client.headers.get("accept-language", "").startswith("en")
        assert client.timeout.connect == 10.0
        assert client.timeout.read == 30.0
        assert client.timeout.write == 30.0
        assert client.timeout.pool == 30.0
        assert client.follow_redirects is True
        assert client.max_redirects == 5
    finally:
        # AsyncClient.close() is async; the constructor merely allocated state.
        pass


@pytest.mark.asyncio
async def test_http_client_sends_user_agent(make_test_http_client, dummy_converter, monkeypatch):
    """AC9 via MockTransport: UA + Accept headers reach the server."""

    _patch_run_docling(monkeypatch, markdown="# x\n", metadata={})

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
