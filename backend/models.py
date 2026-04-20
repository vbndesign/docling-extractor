"""Domain dataclasses for the docling extractor.

All dataclasses are `frozen=True` to make results hashable and safe to share
across async tasks. `Optional` metadata fields default to `None` — consumers
(e.g., the frontmatter writer) omit the YAML key when the value is `None`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

SourceKind = Literal["url_html", "url_pdf", "pdf_upload", "pdf_local_path"]


@dataclass(frozen=True)
class ExtractedMetadata:
    """Metadata detected by Docling or by the HTML head parser."""

    source_title: str | None = None
    author: str | None = None
    year: int | None = None


@dataclass(frozen=True)
class SourceDescriptor:
    """Describes the origin of an extraction request.

    `location` is the URL for remote sources, the absolute path for local
    files, or the original filename for uploads. `original_filename` is only
    populated for `pdf_upload` and `pdf_local_path`.
    """

    kind: SourceKind
    location: str
    original_filename: str | None = None


@dataclass(frozen=True)
class ExtractionResult:
    """Output of `docling_service.extract`.

    ``partial`` + ``failed_pages`` were added in Story 1.7 to describe
    PDF chunked conversions where a subset of pages failed. For the
    regular (single-call) path and for HTML sources, ``partial`` is
    ``False`` and ``failed_pages`` is ``()``.

    ``total_pages`` reports the source PDF's page count when known; it
    stays ``None`` for non-PDF and for legacy/test inputs that never
    passed through the chunker probe. Consumers that render
    "X of Y pages failed" should fall back to ``len(failed_pages)``
    when ``total_pages`` is ``None``.
    """

    markdown: str
    metadata: ExtractedMetadata
    source: SourceDescriptor
    partial: bool = False
    failed_pages: tuple[int, ...] = ()
    total_pages: int | None = None


@dataclass(frozen=True)
class SaveResult:
    """Output of `file_writer.save` — returned by the `/extract` endpoint."""

    output_path: Path
    filename: str
    partial: bool = False
    failed_pages: tuple[int, ...] = ()
    total_pages: int | None = None
