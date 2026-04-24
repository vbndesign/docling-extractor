"""Integration tests for `POST /extract` and friends.

The fixtures in ``conftest.py`` mock the CPU-bound pieces (DocumentConverter,
``_run_docling``) and the HTTP client so every case here runs fully offline
in milliseconds. Cover:

* 4 success paths — URL HTML, URL PDF, upload PDF, local_path PDF (AC7/AC8).
* 7 failure paths — no input, multiple inputs, oversized upload, unreachable
  URL, local_path missing, local_path not PDF, timeout (AC7).
* 4 content-negotiation paths — no Accept, ``application/json``,
  ``text/html`` success, ``text/html`` error (AC9).
* ``/health`` sanity after lifespan mounts.
"""

from __future__ import annotations

import io
import json
import time
from pathlib import Path

import httpx
import pypdfium2 as pdfium
import pytest

HTML_BODY = (
    b"<html><head><title>Sample Article Title</title>"
    b"<meta name='author' content='Jane Doe'></head>"
    b"<body><p>Hi.</p></body></html>"
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _assert_file_has_frontmatter_and_body(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), text[:40]
    _, frontmatter, body = text.split("---", 2)
    assert "note_type: literature_document" in frontmatter
    assert "generated_by: docling" in frontmatter
    assert body.strip(), "body must be non-empty"


# --------------------------------------------------------------------------- #
# /health (regression after lifespan + mounts)
# --------------------------------------------------------------------------- #


def test_health_endpoint_returns_ok(test_client):
    response = test_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# --------------------------------------------------------------------------- #
# GET / (Story 1.5 AC1 — index.html renders with output_dir in context)
# --------------------------------------------------------------------------- #


def test_index_renders_html_shell(test_client, test_settings):
    response = test_client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    body = response.text
    # HTMX is vendored (arch §7.3 — not CDN)
    assert "/static/htmx.min.js" in body
    assert "/static/style.css" in body
    # The three input modes are all rendered in a single page (AC2)
    assert 'name="url"' in body
    assert 'name="file"' in body
    assert 'name="local_path"' in body
    # Output dir from settings is exposed in the header (§5.1)
    assert str(test_settings.output_dir) in body


# --------------------------------------------------------------------------- #
# 4 SUCCESS CASES (AC7 + AC8)
# --------------------------------------------------------------------------- #


def test_extract_url_html_success(test_client, install_http_client, test_settings):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "HEAD":
            return httpx.Response(200, headers={"content-type": "text/html; charset=utf-8"})
        return httpx.Response(200, content=HTML_BODY, headers={"content-type": "text/html"})

    install_http_client(handler)

    response = test_client.post("/extract", data={"url": "https://example.com/article"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ok"
    output_path = Path(body["output_path"])
    assert output_path.is_file()
    assert output_path.parent == test_settings.output_dir.resolve()
    assert output_path.name == body["filename"]
    _assert_file_has_frontmatter_and_body(output_path)


def test_extract_url_pdf_success(test_client, install_http_client, sample_pdf_bytes, test_settings):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "HEAD":
            return httpx.Response(200, headers={"content-type": "application/pdf"})
        return httpx.Response(
            200, content=sample_pdf_bytes, headers={"content-type": "application/pdf"}
        )

    install_http_client(handler)

    response = test_client.post("/extract", data={"url": "https://example.com/paper.pdf"})

    assert response.status_code == 200, response.text
    body = response.json()
    output_path = Path(body["output_path"])
    assert output_path.is_file()
    assert output_path.parent == test_settings.output_dir.resolve()
    _assert_file_has_frontmatter_and_body(output_path)


def test_extract_upload_pdf_success(test_client, sample_pdf_bytes, test_settings):
    files = {"file": ("sample.pdf", sample_pdf_bytes, "application/pdf")}
    response = test_client.post("/extract", files=files)

    assert response.status_code == 200, response.text
    body = response.json()
    output_path = Path(body["output_path"])
    assert output_path.is_file()
    assert output_path.parent == test_settings.output_dir.resolve()
    _assert_file_has_frontmatter_and_body(output_path)


def test_extract_local_path_success(test_client, sample_pdf_path, test_settings):
    response = test_client.post("/extract", data={"local_path": str(sample_pdf_path.resolve())})

    assert response.status_code == 200, response.text
    body = response.json()
    output_path = Path(body["output_path"])
    assert output_path.is_file()
    assert output_path.parent == test_settings.output_dir.resolve()
    _assert_file_has_frontmatter_and_body(output_path)


# --------------------------------------------------------------------------- #
# 7 FAILURE CASES (AC7)
# --------------------------------------------------------------------------- #


def test_extract_no_input_returns_400(test_client):
    response = test_client.post("/extract")
    assert response.status_code == 400
    body = response.json()
    assert body["status"] == "error"
    assert body["code"] == "INVALID_INPUT"
    assert body["hint"]


def test_extract_multiple_inputs_returns_400(test_client, sample_pdf_bytes):
    response = test_client.post(
        "/extract",
        data={"url": "https://example.com/x"},
        files={"file": ("x.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_INPUT"


def test_extract_oversized_upload_maps_to_413(test_client, test_settings):
    # test_settings limits to 1 MB; craft a 2 MB payload that still starts with %PDF-.
    oversized = b"%PDF-" + b"x" * (2 * 1024 * 1024)
    files = {"file": ("big.pdf", oversized, "application/pdf")}
    response = test_client.post("/extract", files=files)
    assert response.status_code == 413
    assert response.json()["code"] == "UPLOAD_TOO_LARGE"


def test_extract_url_returns_404_maps_to_502(test_client, install_http_client):
    # Story 1.6 AC1 caso (a): upstream 404 surfaces to the caller as 502
    # SOURCE_FETCH_FAILED — we do not fabricate 404s from the extractor's
    # own envelope since the origin *responded*, it just didn't have the doc.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    install_http_client(handler)

    response = test_client.post("/extract", data={"url": "https://example.com/missing"})
    assert response.status_code == 502, response.text
    assert response.json()["code"] == "SOURCE_FETCH_FAILED"


def test_extract_local_path_strips_surrounding_quotes(test_client, sample_pdf_path, test_settings):
    # Windows Explorer's "Copy as path" wraps paths in double quotes; the
    # endpoint must accept that natural paste form (AC8 hardening).
    quoted = f'"{sample_pdf_path.resolve()}"'
    response = test_client.post("/extract", data={"local_path": quoted})

    assert response.status_code == 200, response.text
    output_path = Path(response.json()["output_path"])
    assert output_path.is_file()
    assert output_path.parent == test_settings.output_dir.resolve()


def test_extract_local_path_nonexistent_returns_400(test_client, tmp_path):
    missing = tmp_path / "nope.pdf"
    response = test_client.post("/extract", data={"local_path": str(missing)})
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_INPUT"


def test_extract_local_path_not_pdf_returns_400(test_client, tmp_path):
    decoy = tmp_path / "note.txt"
    decoy.write_text("not a pdf")
    response = test_client.post("/extract", data={"local_path": str(decoy)})
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_INPUT"


def test_extract_conversion_timeout_maps_to_504(
    test_client, set_run_docling, sample_pdf_bytes, test_settings
):
    # Override the request timeout to 1 s and make _run_docling sleep 2 s.
    from backend.config import Settings, get_settings

    tight = Settings(
        output_dir=test_settings.output_dir,
        max_upload_mb=test_settings.max_upload_mb,
        request_timeout_seconds=1,
        pdf_chunk_size=test_settings.pdf_chunk_size,
        pdf_chunk_threshold=test_settings.pdf_chunk_threshold,
        max_failed_pages_ratio=test_settings.max_failed_pages_ratio,
    )
    test_client.app.dependency_overrides[get_settings] = lambda: tight

    def slow(source, *, converter):  # noqa: ARG001
        time.sleep(2)
        return "# x\n", {}, []

    set_run_docling(slow)

    files = {"file": ("sample.pdf", sample_pdf_bytes, "application/pdf")}
    response = test_client.post("/extract", files=files)
    assert response.status_code == 504, response.text
    assert response.json()["code"] == "REQUEST_TIMEOUT"


# --------------------------------------------------------------------------- #
# 4 CONTENT NEGOTIATION CASES (AC9)
# --------------------------------------------------------------------------- #


def test_extract_returns_json_when_no_accept_header(test_client, sample_pdf_bytes):
    response = test_client.post(
        "/extract",
        files={"file": ("sample.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")


def test_extract_returns_json_when_accept_application_json(test_client, sample_pdf_bytes):
    response = test_client.post(
        "/extract",
        files={"file": ("sample.pdf", sample_pdf_bytes, "application/pdf")},
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")


def test_extract_returns_html_when_accept_text_html_on_success(test_client, sample_pdf_bytes):
    response = test_client.post(
        "/extract",
        files={"file": ("sample.pdf", sample_pdf_bytes, "application/pdf")},
        headers={"Accept": "text/html"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "result-card--success" in response.text
    assert ".md" in response.text  # filename rendered in partial


def test_extract_returns_html_when_accept_text_html_on_error(test_client):
    response = test_client.post("/extract", headers={"Accept": "text/html"})
    assert response.status_code == 400
    assert response.headers["content-type"].startswith("text/html")
    assert "result-card--error" in response.text
    assert "INVALID_INPUT" in response.text


def test_extract_returns_html_when_htmx_request_without_accept_html(test_client, sample_pdf_bytes):
    # HTMX does not set Accept: text/html on XHR (browser default is */*);
    # HX-Request: true is the reliable signal that the caller wants the
    # server-rendered partial. Without this contract, the frontend would
    # receive raw JSON and render "{...}" into #result.
    response = test_client.post(
        "/extract",
        files={"file": ("sample.pdf", sample_pdf_bytes, "application/pdf")},
        headers={"Accept": "*/*", "HX-Request": "true"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "result-card--success" in response.text


def test_extract_returns_html_when_htmx_request_on_error(test_client):
    response = test_client.post("/extract", headers={"Accept": "*/*", "HX-Request": "true"})
    assert response.status_code == 400
    assert response.headers["content-type"].startswith("text/html")
    assert "result-card--error" in response.text
    assert "INVALID_INPUT" in response.text


# --------------------------------------------------------------------------- #
# AC8 detail — content validation already covered by success tests via
# `_assert_file_has_frontmatter_and_body`. Assert explicitly once more for
# the upload path so a failed frontmatter regression jumps out.
# --------------------------------------------------------------------------- #


def test_extract_upload_pdf_writes_valid_frontmatter(test_client, sample_pdf_bytes, test_settings):
    files = {"file": ("sample.pdf", sample_pdf_bytes, "application/pdf")}
    response = test_client.post("/extract", files=files)
    assert response.status_code == 200
    output_path = Path(response.json()["output_path"])
    text = output_path.read_text(encoding="utf-8")
    assert "note_type: literature_document" in text
    assert "extracted_at:" in text
    assert "created:" in text
    assert "location:" in text
    assert "generated_by: docling" in text


@pytest.mark.parametrize("bad_value", ["", "   "])
def test_extract_rejects_empty_string_url(test_client, bad_value):
    # Belt-and-suspenders for the len(provided) == 1 validator.
    response = test_client.post("/extract", data={"url": bad_value})
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_INPUT"


# --------------------------------------------------------------------------- #
# CORNER CASES (Story 1.6 AC1/AC2)
# --------------------------------------------------------------------------- #


def test_extract_empty_html_maps_to_422(test_client, install_http_client, set_run_docling):
    # Story 1.6 AC1 caso (b): a JS-rendered SPA serves a mostly empty HTML
    # shell; Docling sees no text nodes and returns an empty markdown. The
    # service must surface CONVERSION_FAILED with a clear SPA hint instead
    # of writing a .md file with only frontmatter.
    empty_shell = b"<html><body></body></html>"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "HEAD":
            return httpx.Response(200, headers={"content-type": "text/html"})
        return httpx.Response(200, content=empty_shell, headers={"content-type": "text/html"})

    install_http_client(handler)
    set_run_docling(lambda source, *, converter: ("", {}, []))  # noqa: ARG005

    response = test_client.post("/extract", data={"url": "https://spa.example.com/"})
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["code"] == "CONVERSION_FAILED"
    assert "SPA" in body["message"] or "JavaScript" in body["message"]


def test_extract_scanned_pdf_maps_to_422_with_ocr_hint(test_client, set_run_docling, fixtures_dir):
    # Story 1.6 AC1 caso (c) + AC2: the scanned.pdf fixture is a valid 1-page
    # PDF with zero text runs. _run_docling is stubbed to return empty
    # markdown (simulating no OCR), and the service must reject with an
    # OCR-specific message rather than producing a .md with an empty body.
    set_run_docling(lambda source, *, converter: ("", {}, []))  # noqa: ARG005

    scanned = fixtures_dir / "scanned.pdf"
    with scanned.open("rb") as fh:
        files = {"file": ("scanned.pdf", fh.read(), "application/pdf")}
    response = test_client.post("/extract", files=files)

    assert response.status_code == 422, response.text
    body = response.json()
    assert body["code"] == "CONVERSION_FAILED"
    assert "OCR" in body["message"]
    assert "v1" in body["message"]


def test_extract_non_pdf_file_maps_to_400(test_client):
    # Story 1.6 AC1 caso (d): a user uploads a .txt (or any non-PDF) via the
    # "file" field. The %PDF- magic-byte check in docling_service rejects it
    # with INVALID_INPUT long before Docling is ever invoked.
    files = {"file": ("note.txt", b"this is plain text, not a pdf", "text/plain")}
    response = test_client.post("/extract", files=files)

    assert response.status_code == 400, response.text
    body = response.json()
    assert body["code"] == "INVALID_INPUT"
    assert "PDF" in body["message"]


# --------------------------------------------------------------------------- #
# STORY 1.7 — Chunked PDF extraction (AC7b, AC7c, AC7d)
# --------------------------------------------------------------------------- #


def _native_text_from_chunk(data: bytes) -> str:
    """Extract concatenated native text from every page of an in-memory PDF.

    Mirrors the measurement used by ``tests/fixtures/generate_large_pdf.py``
    so that when the chunked pipeline's mock returns native text per chunk,
    the final markdown char count closely tracks the committed baseline.
    """

    doc = pdfium.PdfDocument(io.BytesIO(data))
    try:
        parts: list[str] = []
        for page in doc:
            tp = page.get_textpage()
            try:
                n = tp.count_chars()
                if n:
                    parts.append(tp.get_text_range(index=0, count=n))
            finally:
                tp.close()
            page.close()
        return "\n".join(parts)
    finally:
        doc.close()


def test_extract_large_pdf_succeeds_with_full_coverage(test_client, set_run_docling, fixtures_dir):
    """AC2 / AC7b — 104-page PDF converts with ≥90% of native-extractable chars.

    The mock stands in for Docling's real pipeline by returning the native
    text of each chunk (read via pypdfium2), which represents a best-case
    chunked conversion. The assertion is loose enough (0.90) to allow for
    whitespace differences between pypdfium2's per-page text and the final
    concatenated markdown, while strict enough to catch any regression that
    drops a chunk silently (which would immediately trip well below 0.90).
    """

    baseline = json.loads((fixtures_dir / "large_text.baseline.json").read_text(encoding="utf-8"))
    assert baseline["total_pages"] >= 100, "fixture must be a >=100-page PDF"

    def native_text_stub(source_for_docling, *, converter):  # noqa: ARG001
        text = _native_text_from_chunk(source_for_docling.stream.getvalue())
        return text, {}, []

    set_run_docling(native_text_stub)

    pdf_bytes = (fixtures_dir / "large_text.pdf").read_bytes()
    files = {"file": ("large_text.pdf", pdf_bytes, "application/pdf")}
    response = test_client.post("/extract", files=files)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["partial"] is False
    assert body["failed_pages"] == []
    assert body["total_pages"] == baseline["total_pages"]

    output_path = Path(body["output_path"])
    text = output_path.read_text(encoding="utf-8")
    body_md = text.split("---", 2)[2]
    ratio = len(body_md.strip()) / baseline["native_text_chars"]
    assert ratio >= 0.90, (
        f"Chunked extraction recovered {ratio:.2%} of native text "
        f"(baseline {baseline['native_text_chars']} chars); expected ≥90%."
    )

    # AC4 — clean conversion MUST NOT emit `partial:` in the frontmatter.
    frontmatter = text.split("---", 2)[1]
    assert "partial:" not in frontmatter
    assert "failed_pages:" not in frontmatter


def test_extract_partial_pdf_returns_200_with_warning(test_client, set_run_docling, fixtures_dir):
    """AC3c, AC4, AC5, AC7c — partial conversion surfaces partial + failed_pages.

    Mock fails pages 3 and 4 of chunk 2 (→ global pages 13, 14 with
    chunk_size=10), well under the default 10% threshold. The endpoint
    MUST return HTTP 200 with `partial: true` + `failed_pages: [13, 14]`
    in JSON, and the written .md frontmatter MUST carry the same keys.
    """

    def failing_chunk2(source_for_docling, *, converter):  # noqa: ARG001
        name = source_for_docling.name
        text = _native_text_from_chunk(source_for_docling.stream.getvalue())
        failed = [3, 4] if "#chunk002" in name else []
        return text, {}, failed

    set_run_docling(failing_chunk2)

    pdf_bytes = (fixtures_dir / "large_text.pdf").read_bytes()
    files = {"file": ("large_text.pdf", pdf_bytes, "application/pdf")}
    response = test_client.post("/extract", files=files)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["partial"] is True
    assert body["failed_pages"] == [13, 14]
    assert body["total_pages"] == 104

    # AC4 — frontmatter carries partial + failed_pages in block form.
    output_path = Path(body["output_path"])
    text = output_path.read_text(encoding="utf-8")
    frontmatter = text.split("---", 2)[1]
    assert "partial: true" in frontmatter
    assert "failed_pages:" in frontmatter
    assert "- 13" in frontmatter
    assert "- 14" in frontmatter


def test_extract_partial_pdf_renders_htmx_warning_block(test_client, set_run_docling, fixtures_dir):
    """AC5 — HTMX response includes a visual warning block listing failed pages."""

    def failing_chunk2(source_for_docling, *, converter):  # noqa: ARG001
        name = source_for_docling.name
        text = _native_text_from_chunk(source_for_docling.stream.getvalue())
        failed = [3, 4] if "#chunk002" in name else []
        return text, {}, failed

    set_run_docling(failing_chunk2)

    pdf_bytes = (fixtures_dir / "large_text.pdf").read_bytes()
    files = {"file": ("large_text.pdf", pdf_bytes, "application/pdf")}
    response = test_client.post(
        "/extract",
        files=files,
        headers={"Accept": "text/html"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    html = response.text
    assert "result-card--success" in html
    assert "partial-notice" in html
    assert "PARTIAL_EXTRACTION" in html
    # The list of failed pages must actually show the document-wide numbers,
    # not the chunk-relative ones — if the offset were dropped we'd see
    # "3, 4" instead of "13, 14".
    assert "13, 14" in html


def test_extract_pdf_exceeds_failure_threshold_returns_422(
    test_client, set_run_docling, fixtures_dir
):
    """AC3b, AC7d — above MAX_FAILED_PAGES_RATIO → HTTP 422 CONVERSION_FAILED."""

    def fail_half(source_for_docling, *, converter):  # noqa: ARG001
        # Fail pages 1-5 of every 10-page chunk → 50% of pages across the doc,
        # well above the default 10% ratio.
        text = _native_text_from_chunk(source_for_docling.stream.getvalue())
        return text, {}, [1, 2, 3, 4, 5]

    set_run_docling(fail_half)

    pdf_bytes = (fixtures_dir / "large_text.pdf").read_bytes()
    files = {"file": ("large_text.pdf", pdf_bytes, "application/pdf")}
    response = test_client.post("/extract", files=files)

    assert response.status_code == 422, response.text
    body = response.json()
    assert body["code"] == "CONVERSION_FAILED"
    assert "over threshold" in body["message"]


# --------------------------------------------------------------------------- #
# STORY 1.8 — DOCX input support (AC4, AC5, AC8)
# --------------------------------------------------------------------------- #


def test_extract_upload_docx_success(test_client, fixtures_dir, test_settings, set_run_docling):
    """AC4a, AC8d — upload of a ``.docx`` via the existing ``file`` form field."""

    set_run_docling(lambda source, *, converter: ("# DOCX body\n\nFirst paragraph.\n", {}, []))  # noqa: ARG005
    docx_bytes = (fixtures_dir / "sample.docx").read_bytes()

    files = {
        "file": (
            "sample.docx",
            docx_bytes,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    }
    response = test_client.post("/extract", files=files)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ok"
    output_path = Path(body["output_path"])
    assert output_path.is_file()
    assert output_path.parent == test_settings.output_dir.resolve()
    # AC6 — .docx → .md, never .docx.md
    assert output_path.suffix == ".md"
    assert ".docx" not in output_path.name
    _assert_file_has_frontmatter_and_body(output_path)


def test_extract_local_path_docx_success(test_client, fixtures_dir, test_settings, set_run_docling):
    """AC4b — ``local_path`` accepts ``.docx`` with ZIP magic bytes."""

    set_run_docling(lambda source, *, converter: ("# Local DOCX\n\nBody.\n", {}, []))  # noqa: ARG005

    docx_path = fixtures_dir / "sample.docx"
    response = test_client.post("/extract", data={"local_path": str(docx_path.resolve())})

    assert response.status_code == 200, response.text
    body = response.json()
    output_path = Path(body["output_path"])
    assert output_path.is_file()
    assert output_path.parent == test_settings.output_dir.resolve()
    assert output_path.suffix == ".md"
    _assert_file_has_frontmatter_and_body(output_path)


def test_extract_upload_docx_writes_core_properties_into_frontmatter(
    test_client, fixtures_dir, set_run_docling
):
    """AC5 — ``dc:title``, ``dc:creator``, ``dcterms:created`` land in YAML.

    The ``_run_docling`` stub ignores the input stream; the metadata
    assertion relies entirely on ``_parse_docx_core_properties`` reading
    the real fixture bytes attached to the request.
    """

    set_run_docling(lambda source, *, converter: ("# Body\n\nPara.\n", {}, []))  # noqa: ARG005
    docx_bytes = (fixtures_dir / "sample.docx").read_bytes()

    files = {
        "file": (
            "sample.docx",
            docx_bytes,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    }
    response = test_client.post("/extract", files=files)

    assert response.status_code == 200, response.text
    output_path = Path(response.json()["output_path"])
    text = output_path.read_text(encoding="utf-8")
    frontmatter = text.split("---", 2)[1]
    assert "source_title: Docling DOCX Fixture" in frontmatter
    assert "author: Test Author" in frontmatter
    assert "year: 2024" in frontmatter


def test_extract_upload_docx_with_pdf_magic_returns_400(test_client):
    """AC3 (a) — ``.docx`` filename + non-ZIP magic bytes → 400 INVALID_INPUT."""

    # %PDF- header inside a file the caller claims is a DOCX; story AC3a.
    payload = b"%PDF-1.4\n% not really a docx, renamed on disk\n"
    files = {
        "file": (
            "pretend.docx",
            payload,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    }
    response = test_client.post("/extract", files=files)

    assert response.status_code == 400, response.text
    body = response.json()
    assert body["code"] == "INVALID_INPUT"
    assert "docx" in body["message"].lower()
    assert "zip" in body["message"].lower()


def test_extract_upload_invalid_docx_returns_422(test_client, set_run_docling):
    """AC3 (b) — valid ZIP but not an OOXML Word package → Docling raises 422.

    We stub ``_run_docling`` to raise ``ConversionError``, mirroring what
    happens in production when the user uploads a ``.xlsx`` / ``.pptx``
    disguised as ``.docx`` (AC3b: deferred to Docling, surfaces as
    ``CONVERSION_FAILED``).
    """

    from backend.errors import ConversionError

    def _boom(source, *, converter):  # noqa: ARG001
        raise ConversionError("Docling rejected non-Word OOXML package")

    set_run_docling(_boom)

    # Minimal ZIP with at least one entry — an empty ZIP uses the EOCD
    # signature ``PK\x05\x06`` rather than the Local File Header ``PK\x03\x04``
    # the magic-byte check requires. A one-entry ZIP exercises the branch
    # where the upload passes the magic check but Docling refuses the
    # package (AC3b — wrong OOXML flavour surfaces as CONVERSION_FAILED).
    import io as _io
    import zipfile as _zipfile

    buf = _io.BytesIO()
    with _zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("dummy.txt", "not an OOXML package")
    files = {
        "file": (
            "fake.docx",
            buf.getvalue(),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    }
    response = test_client.post("/extract", files=files)

    assert response.status_code == 422, response.text
    assert response.json()["code"] == "CONVERSION_FAILED"


def test_extract_success_emits_partial_false_in_json_response(test_client, sample_pdf_bytes):
    """AC5 / API contract — JSON envelope ALWAYS includes partial/failed_pages.

    Unlike the frontmatter (which omits the keys on clean conversions, per
    FR4), the JSON response carries `partial: false` and `failed_pages: []`
    even on success so API consumers can assume a stable shape.
    """

    files = {"file": ("sample.pdf", sample_pdf_bytes, "application/pdf")}
    response = test_client.post("/extract", files=files)

    assert response.status_code == 200
    body = response.json()
    assert body["partial"] is False
    assert body["failed_pages"] == []
    assert "total_pages" in body
