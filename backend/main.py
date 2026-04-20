"""FastAPI application entry point.

Wires the extraction pipeline behind a single `POST /extract` endpoint and
serves the (Story 1.5) HTMX frontend. Follows the architectural invariants
of arch §2.2, §7, §10:

* `DocumentConverter`, the async HTTP client (curl_cffi, TLS-impersonating),
  and `Jinja2Templates` are lifespan-scoped singletons (R2).
* The endpoint does not use `try/except`; all translation happens in the
  global handlers registered in `backend.errors` (arch §10.3).
* The CPU-bound stages (`build`, `save`) run in the default threadpool via
  `asyncio.to_thread`; the whole call is bounded by
  `asyncio.wait_for(..., timeout=settings.request_timeout_seconds)` (R1).
"""

from __future__ import annotations

import asyncio
import io
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from fastapi import Depends, FastAPI, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import errors
from .config import Settings, get_settings
from .docling_service import PDF_MAGIC, extract, make_http_client
from .errors import (
    InvalidInputError,
    RequestTimeoutError,
    UploadTooLargeError,
)
from .file_writer import save
from .frontmatter import build
from .models import ExtractionResult, SaveResult

if TYPE_CHECKING:
    from .docling_service import HttpClient


FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


class _NamedBytesIO(io.BytesIO):
    """BytesIO carrying a `.name` so downstream DocumentStream can label it."""

    def __init__(self, data: bytes, name: str) -> None:
        super().__init__(data)
        self.name = name


@asynccontextmanager
async def lifespan(app: FastAPI):
    # v1 is a no-OCR tool (README / error catalog): scanned PDFs return 422.
    # Docling defaults `do_ocr=True`, which makes RapidOCR run on every page
    # even for PDFs with native text — ~5–10x slower on CPU and the direct
    # cause of 504s on 100-page PDFs under the Story 1.7 timeout. Disabling
    # it here aligns the runtime with the product stance and matches what
    # the Story 1.7 probes (D1/D2) measured.
    pdf_pipeline_options = PdfPipelineOptions(do_ocr=False)
    app.state.converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_pipeline_options),
        }
    )
    app.state.http_client = make_http_client()
    app.state.templates = Jinja2Templates(directory=str(FRONTEND_DIR / "templates"))
    try:
        yield
    finally:
        # httpx.AsyncClient exposes `aclose`; curl_cffi AsyncSession exposes `close`.
        # Tests inject the former, production uses the latter.
        client = app.state.http_client
        shutdown = getattr(client, "aclose", None) or client.close
        await shutdown()


app = FastAPI(title="Docling Extractor", version="0.1.0", lifespan=lifespan)
app.mount(
    "/static",
    StaticFiles(directory=str(FRONTEND_DIR / "static")),
    name="static",
)
errors.register_handlers(app)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def index(
    request: Request,
    settings: Settings = Depends(get_settings),  # noqa: B008 — FastAPI DI idiom
) -> Response:
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "index.html",
        {"output_dir": str(settings.output_dir)},
    )


def _validate_local_path(raw: str) -> Path:
    """Enforce arch §2.2 R4 for the `local_path` fallback."""

    # Windows Explorer's "Copy as path" wraps paths in double quotes; strip
    # surrounding quotes/whitespace so that natural paste flow works.
    raw = raw.strip().strip('"').strip("'")
    path = Path(raw)
    if not path.is_file():
        raise InvalidInputError(f"local_path does not exist or is not a file: {raw}")
    if path.suffix.lower() != ".pdf":
        raise InvalidInputError(f"local_path must point to a .pdf file: {raw}")
    with path.open("rb") as handle:
        head = handle.read(len(PDF_MAGIC))
    if not head.startswith(PDF_MAGIC):
        raise InvalidInputError(f"local_path is not a valid PDF (missing %PDF- magic bytes): {raw}")
    return path


async def _run_pipeline(
    source: object,
    *,
    http_client: HttpClient,
    converter: DocumentConverter,
    settings: Settings,
) -> SaveResult:
    """Orchestrate extract → build → save for a single request.

    `extract` is async because it performs HTTP I/O via the injected
    client; the pure CPU/IO stages (`build` + `save`) are offloaded to the
    default threadpool so the event loop stays responsive even on large
    files (arch §R1).

    Story 1.7: when ``er.partial`` is true (chunked PDF with some failed
    pages below ``MAX_FAILED_PAGES_RATIO``), propagate ``partial`` +
    ``failed_pages`` both into the frontmatter YAML (for the ``.md`` file
    on disk) and into the ``SaveResult`` (for the API response / HTMX
    template). Total pages flow through too so the UI can say "N of M
    pages failed" without recomputing.
    """

    er: ExtractionResult = await extract(
        source,
        http_client=http_client,
        converter=converter,
        settings=settings,
    )

    def _persist() -> SaveResult:
        fm = build(
            er.metadata,
            er.source,
            now=datetime.now(tz=UTC),
            partial_info=(er.partial, er.failed_pages),
        )
        raw = save(fm, er.markdown, er.metadata, er.source, settings.output_dir)
        return SaveResult(
            output_path=raw.output_path,
            filename=raw.filename,
            partial=er.partial,
            failed_pages=er.failed_pages,
            total_pages=er.total_pages,
        )

    return await asyncio.to_thread(_persist)


@app.post("/extract")
async def extract_endpoint(
    request: Request,
    url: str | None = Form(None),
    file: UploadFile | None = File(None),  # noqa: B008 — FastAPI DI idiom
    local_path: str | None = Form(None),
    settings: Settings = Depends(get_settings),  # noqa: B008 — FastAPI DI idiom
) -> Response:
    # AC1/AC2 — exactly one of the three fields must be provided.
    provided = [
        name for name, value in (("url", url), ("file", file), ("local_path", local_path)) if value
    ]
    if len(provided) != 1:
        raise InvalidInputError(
            "Provide exactly one of: url, file, or local_path "
            f"(received: {', '.join(provided) or 'none'})."
        )

    max_bytes = settings.max_upload_mb * 1024 * 1024

    if url is not None:
        source: object = url
    elif file is not None:
        # AC3 — reject oversized uploads BEFORE reading the body.
        if file.size is not None and file.size > max_bytes:
            raise UploadTooLargeError(f"Upload exceeds {settings.max_upload_mb} MB limit.")
        data = await file.read()
        if len(data) > max_bytes:
            raise UploadTooLargeError(f"Upload exceeds {settings.max_upload_mb} MB limit.")
        source = _NamedBytesIO(data, name=file.filename or "upload.pdf")
    else:
        # local_path branch (fallback FR9).
        assert local_path is not None
        path = _validate_local_path(local_path)
        if path.stat().st_size > max_bytes:
            raise UploadTooLargeError(f"local_path file exceeds {settings.max_upload_mb} MB limit.")
        source = path

    # AC6 — hard timeout around the whole pipeline.
    try:
        save_result = await asyncio.wait_for(
            _run_pipeline(
                source,
                http_client=request.app.state.http_client,
                converter=request.app.state.converter,
                settings=settings,
            ),
            timeout=settings.request_timeout_seconds,
        )
    except TimeoutError as exc:
        raise RequestTimeoutError(
            f"Extraction exceeded REQUEST_TIMEOUT_SECONDS ({settings.request_timeout_seconds}s)."
        ) from exc

    if errors.prefers_html(request):
        templates: Jinja2Templates = request.app.state.templates
        return templates.TemplateResponse(
            request,
            "partials/result_success.html",
            {"result": save_result},
        )
    return JSONResponse(
        status_code=200,
        content={
            "status": "ok",
            "output_path": str(save_result.output_path),
            "filename": save_result.filename,
            # Story 1.7: partial/failed_pages are always present in the
            # JSON envelope (unlike the frontmatter, which omits them on
            # clean conversions). API contract vs. file-on-disk contract
            # intentionally differ — see arch §5.2 vs §7.2.
            "partial": save_result.partial,
            "failed_pages": list(save_result.failed_pages),
            "total_pages": save_result.total_pages,
        },
    )
