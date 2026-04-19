"""Invariants of the global exception handler (arch §10.2 invariants 1-4).

Covers:
* Every ``DoclingExtractorError`` subclass has a `code` registered in
  `ERROR_CATALOG` (invariant 2).
* The JSON envelope is always ``{status, code, message, hint}`` with a
  non-empty `hint` (invariants 1, 3).
* Untyped exceptions are promoted to `INTERNAL_ERROR` with HTTP 500 by
  `unexpected_handler`.
* The HTML and JSON payloads are derived from the same dict (invariant 4):
  whatever keys show up in JSON also appear in the rendered HTML.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend import errors
from backend.errors import (
    ERROR_CATALOG,
    ConversionError,
    DoclingExtractorError,
    InvalidInputError,
    RequestTimeoutError,
    SourceFetchError,
    UploadTooLargeError,
    register_handlers,
)

SUBCLASSES = [
    InvalidInputError,
    UploadTooLargeError,
    SourceFetchError,
    ConversionError,
    RequestTimeoutError,
]


# --------------------------------------------------------------------------- #
# Catalog integrity
# --------------------------------------------------------------------------- #


def test_catalog_has_six_entries():
    assert set(ERROR_CATALOG.keys()) == {
        "INVALID_INPUT",
        "UPLOAD_TOO_LARGE",
        "SOURCE_FETCH_FAILED",
        "CONVERSION_FAILED",
        "REQUEST_TIMEOUT",
        "INTERNAL_ERROR",
    }


@pytest.mark.parametrize("cls", SUBCLASSES)
def test_every_subclass_code_is_in_catalog(cls):
    assert cls.code in ERROR_CATALOG


def test_internal_error_is_default_code():
    assert DoclingExtractorError.code == "INTERNAL_ERROR"
    assert DoclingExtractorError.http_status == 500


def test_every_catalog_hint_is_non_empty():
    for code, (default_msg, hint) in ERROR_CATALOG.items():
        assert default_msg, code
        assert hint, code


# --------------------------------------------------------------------------- #
# Handler behaviour via a minimal FastAPI app
# --------------------------------------------------------------------------- #


def _make_app(exc: Exception) -> FastAPI:
    app = FastAPI()
    templates_dir = str(
        __import__("pathlib").Path(__file__).resolve().parent.parent
        / "frontend"
        / "templates"
    )
    from fastapi.templating import Jinja2Templates

    app.state.templates = Jinja2Templates(directory=templates_dir)
    register_handlers(app)

    @app.get("/boom")
    def boom():
        raise exc

    return app


@pytest.mark.parametrize("cls", SUBCLASSES)
def test_handler_json_envelope_for_each_subclass(cls):
    app = _make_app(cls("custom message"))
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/boom")
    assert response.status_code == cls.http_status
    body = response.json()
    assert body["status"] == "error"
    assert body["code"] == cls.code
    assert body["message"] == "custom message"
    assert body["hint"] == ERROR_CATALOG[cls.code][1]


def test_handler_falls_back_to_default_message_when_exc_has_no_args():
    exc = InvalidInputError()
    app = _make_app(exc)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/boom")
    body = response.json()
    assert body["message"] == ERROR_CATALOG["INVALID_INPUT"][0]


def test_untyped_exception_promoted_to_internal_error():
    app = _make_app(RuntimeError("something broke"))
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/boom")
    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "INTERNAL_ERROR"
    assert body["hint"] == ERROR_CATALOG["INTERNAL_ERROR"][1]


def test_html_and_json_share_the_same_payload():
    app = _make_app(SourceFetchError("URL returned 404."))
    with TestClient(app, raise_server_exceptions=False) as client:
        json_response = client.get("/boom", headers={"Accept": "application/json"})
        html_response = client.get("/boom", headers={"Accept": "text/html"})

    assert json_response.status_code == html_response.status_code == 502

    payload = json_response.json()
    assert payload["code"] == "SOURCE_FETCH_FAILED"
    html = html_response.text
    # Every value from the JSON payload must render into the HTML partial.
    assert payload["code"] in html
    assert payload["message"] in html
    assert payload["hint"] in html


# --------------------------------------------------------------------------- #
# Content negotiation helper
# --------------------------------------------------------------------------- #


class _FakeRequest:
    def __init__(self, accept: str | None, hx_request: str | None = None) -> None:
        self.headers: dict[str, str] = {}
        if accept is not None:
            self.headers["accept"] = accept
        if hx_request is not None:
            self.headers["hx-request"] = hx_request


@pytest.mark.parametrize(
    ("accept", "hx_request", "expected"),
    [
        # Baseline Accept-only behaviour (no HX-Request).
        (None, None, False),
        ("", None, False),
        ("*/*", None, False),
        ("application/json", None, False),
        ("application/json, text/html", None, False),
        ("text/html", None, True),
        ("text/html, application/xhtml+xml", None, True),
        # HTMX signal — browser default Accept is "*/*", so HX-Request is the
        # reliable hint. HTMX requests must get the HTML partial.
        ("*/*", "true", True),
        ("", "true", True),
        (None, "true", True),
        # Explicit JSON Accept wins even if HX-Request is set (CLI-style override).
        ("application/json", "true", False),
        # HX-Request: false (not emitted by HTMX, defensive check).
        ("*/*", "false", False),
    ],
)
def test_prefers_html_precedence(accept, hx_request, expected):
    assert errors.prefers_html(_FakeRequest(accept, hx_request)) is expected
