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

import time
from pathlib import Path

import httpx
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
    )
    test_client.app.dependency_overrides[get_settings] = lambda: tight

    def slow(source, *, converter):  # noqa: ARG001
        time.sleep(2)
        return "# x\n", {}

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
    set_run_docling(lambda source, *, converter: ("", {}))  # noqa: ARG005

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
    set_run_docling(lambda source, *, converter: ("", {}))  # noqa: ARG005

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
