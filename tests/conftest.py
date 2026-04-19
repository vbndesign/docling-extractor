"""Shared pytest fixtures.

Only fixtures intended for multiple test modules live here. Module-local
fixtures stay in their own files.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

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


@pytest.fixture
def test_settings(tmp_path: Path):
    """Settings instance pointed at a per-test output dir with tight limits."""

    from backend.config import Settings

    return Settings(
        output_dir=tmp_path / "out",
        max_upload_mb=1,
        request_timeout_seconds=5,
    )


def _default_run_docling_stub(markdown: str, metadata: dict):
    def _stub(source, *, converter):  # noqa: ARG001
        return markdown, dict(metadata)

    return _stub


@pytest.fixture
def test_client(
    monkeypatch: pytest.MonkeyPatch,
    test_settings,
) -> Iterator[TestClient]:
    """FastAPI `TestClient` with a mocked lifespan.

    * `DocumentConverter` is replaced with a sentinel so the real Docling
      pipeline (~600 MB download on first boot) never fires.
    * `make_http_client` returns an `AsyncClient` backed by an in-memory
      `MockTransport` that 404s by default — individual tests swap
      `app.state.http_client` when they need a specific handler.
    * `_run_docling` returns a canned `(markdown, metadata)` pair; tests
      override it with their own stub when needed.
    * `get_settings` is overridden to `test_settings` (tmp output dir).
    """

    from backend import main as backend_main
    from backend.config import get_settings

    class _DummyConverterForApp:
        pass

    monkeypatch.setattr(backend_main, "DocumentConverter", _DummyConverterForApp)

    def _inert_http_client() -> httpx.AsyncClient:
        transport = httpx.MockTransport(lambda req: httpx.Response(404))
        return httpx.AsyncClient(transport=transport, timeout=5.0)

    monkeypatch.setattr(backend_main, "make_http_client", _inert_http_client)

    from backend import docling_service

    monkeypatch.setattr(
        docling_service,
        "_run_docling",
        _default_run_docling_stub("# Sample\n\nBody.\n", {"source_title": "Sample"}),
    )

    backend_main.app.dependency_overrides[get_settings] = lambda: test_settings
    try:
        with TestClient(backend_main.app) as client:
            yield client
    finally:
        backend_main.app.dependency_overrides.pop(get_settings, None)


@pytest.fixture
def install_http_client(test_client):
    """Replace `app.state.http_client` with a MockTransport-backed AsyncClient.

    The previously-installed client is left for garbage collection — the
    final one on `app.state` is closed by the lifespan shutdown hook.
    """

    from backend.docling_service import HTTP_USER_AGENT

    def _install(handler: Callable[[httpx.Request], httpx.Response]) -> None:
        new_client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            headers={"User-Agent": HTTP_USER_AGENT},
            timeout=httpx.Timeout(30.0, connect=10.0),
            follow_redirects=True,
            max_redirects=5,
        )
        test_client.app.state.http_client = new_client

    return _install


@pytest.fixture
def set_run_docling(monkeypatch: pytest.MonkeyPatch):
    """Factory to rebind `_run_docling` to a custom stub mid-test."""

    from backend import docling_service

    def _factory(stub) -> None:
        monkeypatch.setattr(docling_service, "_run_docling", stub)

    return _factory
