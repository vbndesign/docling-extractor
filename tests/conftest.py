"""Shared pytest fixtures.

Only fixtures intended for multiple test modules live here. Module-local
fixtures stay in their own files.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def sample_html_path() -> Path:
    return FIXTURES_DIR / "sample.html"


@pytest.fixture
def sample_pdf_path() -> Path:
    return FIXTURES_DIR / "sample.pdf"


@pytest.fixture
def sample_html_bytes(sample_html_path: Path) -> bytes:
    return sample_html_path.read_bytes()


@pytest.fixture
def sample_pdf_bytes(sample_pdf_path: Path) -> bytes:
    return sample_pdf_path.read_bytes()


@pytest.fixture
def mock_docling_result() -> tuple[str, dict]:
    """Canonical (markdown, metadata) pair returned by a mocked `_run_docling`."""

    return (
        "# Sample Article Title\n\nBody paragraph extracted by the mock.\n",
        {"source_title": "Sample Article Title"},
    )


Handler = Callable[[httpx.Request], httpx.Response]


@pytest.fixture
def make_mock_transport() -> Callable[[Handler], httpx.MockTransport]:
    """Factory that wraps a handler callable into an `httpx.MockTransport`."""

    def _factory(handler: Handler) -> httpx.MockTransport:
        return httpx.MockTransport(handler)

    return _factory


@pytest.fixture
def make_test_http_client(make_mock_transport):
    """Builds an `httpx.AsyncClient` whose transport is under the test's control.

    The production config (User-Agent, timeout, redirect cap) is mirrored
    so assertions about those headers remain meaningful.
    """

    from backend.docling_service import HTTP_USER_AGENT

    def _factory(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=make_mock_transport(handler),
            headers={"User-Agent": HTTP_USER_AGENT},
            timeout=httpx.Timeout(30.0, connect=10.0),
            follow_redirects=True,
            max_redirects=5,
        )

    return _factory


class _DummyConverter:
    """Sentinel object injected in place of a real `DocumentConverter`.

    Tests monkeypatch `_run_docling` so the converter is never invoked;
    using a dummy keeps the injection contract explicit.
    """


@pytest.fixture
def dummy_converter() -> _DummyConverter:
    return _DummyConverter()
