"""Unit tests for `backend.file_writer.save`.

Tests use ``tmp_path`` as the output directory and pass a deterministic
``now`` so the empty-slug fallback (R9) produces stable assertions.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from backend.file_writer import save
from backend.models import ExtractedMetadata, SaveResult, SourceDescriptor

FRONTMATTER = "---\nnote_type: literature_document\n---"
BODY = "# Body\n\nSome paragraph.\n"


@pytest.fixture
def fixed_now() -> datetime:
    return datetime(2026, 4, 19, 10, 0, 0, tzinfo=UTC)


def _read_written(result: SaveResult) -> str:
    return result.output_path.read_text(encoding="utf-8")


def test_save_uses_title_as_filename(tmp_path: Path, fixed_now: datetime) -> None:
    """AC6 — `metadata.source_title` wins over every other source of name."""

    metadata = ExtractedMetadata(source_title="My Great Article")
    source = SourceDescriptor(
        kind="pdf_upload",
        location="ignored.pdf",
        original_filename="ignored.pdf",
    )

    result = save(FRONTMATTER, BODY, metadata, source, tmp_path, now=fixed_now)

    assert result.filename == "my-great-article.md"
    assert result.output_path.is_file()
    assert _read_written(result) == FRONTMATTER + "\n" + BODY


def test_save_uses_original_filename_when_no_title(
    tmp_path: Path, fixed_now: datetime
) -> None:
    """AC6 — for PDF sources without a title, fall back to the upload's stem."""

    metadata = ExtractedMetadata()
    source = SourceDescriptor(
        kind="pdf_upload",
        location="paper draft FINAL.pdf",
        original_filename="paper draft FINAL.pdf",
    )

    result = save(FRONTMATTER, BODY, metadata, source, tmp_path, now=fixed_now)

    assert result.filename == "paper-draft-final.md"


def test_save_uses_url_slug_when_no_title_and_no_filename(
    tmp_path: Path, fixed_now: datetime
) -> None:
    """AC6 — the last URL path segment becomes the filename when nothing else exists."""

    metadata = ExtractedMetadata()
    source = SourceDescriptor(
        kind="url_html",
        location="https://example.com/artigos/meu-post",
    )

    result = save(FRONTMATTER, BODY, metadata, source, tmp_path, now=fixed_now)

    assert result.filename == "meu-post.md"


def test_save_applies_kebab_case_slug(tmp_path: Path, fixed_now: datetime) -> None:
    """AC6 — special chars become ASCII kebab-case."""

    metadata = ExtractedMetadata(source_title="Olá! Açaí & Café — São Paulo")
    source = SourceDescriptor(kind="url_html", location="https://example.com/x")

    result = save(FRONTMATTER, BODY, metadata, source, tmp_path, now=fixed_now)

    assert result.filename == "ola-acai-cafe-sao-paulo.md"


def test_save_collision_appends_incremental_suffix(
    tmp_path: Path, fixed_now: datetime
) -> None:
    """AC7 — saving the same name three times yields `.md`, `-2.md`, `-3.md`."""

    metadata = ExtractedMetadata(source_title="Same Title")
    source = SourceDescriptor(kind="url_html", location="https://example.com/x")

    first = save(FRONTMATTER, BODY, metadata, source, tmp_path, now=fixed_now)
    second = save(FRONTMATTER, BODY, metadata, source, tmp_path, now=fixed_now)
    third = save(FRONTMATTER, BODY, metadata, source, tmp_path, now=fixed_now)

    assert first.filename == "same-title.md"
    assert second.filename == "same-title-2.md"
    assert third.filename == "same-title-3.md"
    assert {p.name for p in tmp_path.iterdir()} == {
        "same-title.md",
        "same-title-2.md",
        "same-title-3.md",
    }


def test_save_long_title_truncated_to_200_chars(
    tmp_path: Path, fixed_now: datetime
) -> None:
    """arch §2.2 R5 — slug is capped at 200 chars before suffix + extension."""

    long_title = "word " * 80  # 400 chars of content, slugify will cut to 200
    metadata = ExtractedMetadata(source_title=long_title)
    source = SourceDescriptor(kind="url_html", location="https://example.com/x")

    result = save(FRONTMATTER, BODY, metadata, source, tmp_path, now=fixed_now)
    stem = result.output_path.stem

    assert len(stem) <= 200


def test_save_empty_slug_fallback(tmp_path: Path, fixed_now: datetime) -> None:
    """arch §2.2 R9 — pure-symbol titles produce ``document-{timestamp}``."""

    metadata = ExtractedMetadata(source_title="!@#$%^&*()")
    source = SourceDescriptor(kind="url_html", location="https://example.com/!@#")

    result = save(FRONTMATTER, BODY, metadata, source, tmp_path, now=fixed_now)
    expected_ts = int(fixed_now.timestamp())

    assert result.filename == f"document-{expected_ts}.md"


def test_save_returns_absolute_path_and_filename(
    tmp_path: Path, fixed_now: datetime
) -> None:
    """AC6 — `output_path` is absolute and `filename` is the basename."""

    metadata = ExtractedMetadata(source_title="Absolute Path Check")
    source = SourceDescriptor(kind="url_html", location="https://example.com/x")

    result = save(FRONTMATTER, BODY, metadata, source, tmp_path, now=fixed_now)

    assert result.output_path.is_absolute()
    assert result.output_path.name == result.filename
    assert result.filename == "absolute-path-check.md"
