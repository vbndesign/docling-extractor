"""Unit tests for `backend.frontmatter.build`.

The function is pure, so tests pass deterministic inputs (including a
fixed ``now``) and assert exact YAML output. Round-trip parsing via
``yaml.safe_load`` validates AC5 (special-character escaping).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
import yaml

from backend.frontmatter import build
from backend.models import ExtractedMetadata, SourceDescriptor

REQUIRED_KEYS = {"note_type", "created", "extracted_at", "location", "generated_by"}
FORBIDDEN_KEYS = {"title", "source_type", "domain", "concepts_extracted"}


@pytest.fixture
def fixed_now() -> datetime:
    return datetime(2026, 4, 18, 14, 32, 11, tzinfo=UTC)


@pytest.fixture
def html_source() -> SourceDescriptor:
    return SourceDescriptor(kind="url_html", location="https://example.com/article")


def _strip_delimiters(rendered: str) -> str:
    """Return the inner YAML body so it can be loaded by `yaml.safe_load`."""

    assert rendered.startswith("---\n"), "frontmatter must start with `---\\n`"
    assert rendered.endswith("---"), "frontmatter must end with `---`"
    return rendered[4:-3]


def test_build_all_required_fields_present(fixed_now, html_source) -> None:
    """AC2 — required keys are always emitted, even with no metadata."""

    rendered = build(ExtractedMetadata(), html_source, fixed_now)
    parsed = yaml.safe_load(_strip_delimiters(rendered))

    assert REQUIRED_KEYS.issubset(parsed.keys())
    assert parsed["note_type"] == "literature_document"
    assert parsed["generated_by"] == "docling"
    assert parsed["location"] == "https://example.com/article"


def test_build_all_optional_fields_present(fixed_now, html_source) -> None:
    """AC3 — all optional keys are emitted when populated."""

    metadata = ExtractedMetadata(
        source_title="Example Article Title",
        author="Jane Doe",
        year=2024,
    )
    rendered = build(metadata, html_source, fixed_now)
    parsed = yaml.safe_load(_strip_delimiters(rendered))

    assert parsed["source_title"] == "Example Article Title"
    assert parsed["author"] == "Jane Doe"
    assert parsed["year"] == 2024


def test_build_mixed_optional_fields(fixed_now, html_source) -> None:
    """AC3 — only populated optional keys are emitted; the rest are absent."""

    metadata = ExtractedMetadata(source_title="Only Title", author=None, year=2023)
    rendered = build(metadata, html_source, fixed_now)
    parsed = yaml.safe_load(_strip_delimiters(rendered))

    assert parsed["source_title"] == "Only Title"
    assert parsed["year"] == 2023
    assert "author" not in parsed


def test_build_omits_missing_fields(fixed_now, html_source) -> None:
    """AC3 — `None` is never serialised as `null`, ``""`` or a placeholder."""

    rendered = build(ExtractedMetadata(), html_source, fixed_now)

    assert "source_title" not in rendered
    assert "author" not in rendered
    assert "year" not in rendered
    assert "null" not in rendered.lower()


def test_build_never_includes_forbidden_fields(fixed_now, html_source) -> None:
    """AC4 — `title`, `source_type`, `domain`, `concepts_extracted` never appear."""

    metadata = ExtractedMetadata(source_title="Legit Title", author="Author", year=2024)
    rendered = build(metadata, html_source, fixed_now)
    parsed = yaml.safe_load(_strip_delimiters(rendered))

    for forbidden in FORBIDDEN_KEYS:
        assert forbidden not in parsed, f"forbidden key `{forbidden}` leaked into output"


def test_build_escapes_special_chars(fixed_now) -> None:
    """AC5 — quotes, colons, and Windows backslashes survive a YAML round-trip."""

    nasty_title = 'A: "title" with \\backslashes\\ and: colons'
    nasty_author = 'O\'Brien, "M."'
    metadata = ExtractedMetadata(source_title=nasty_title, author=nasty_author)
    source = SourceDescriptor(
        kind="pdf_local_path",
        location=r"C:\Users\vbnde\Docs\some: file.pdf",
        original_filename="some: file.pdf",
    )

    rendered = build(metadata, source, fixed_now)
    parsed = yaml.safe_load(_strip_delimiters(rendered))

    assert parsed["source_title"] == nasty_title
    assert parsed["author"] == nasty_author
    assert parsed["location"] == r"C:\Users\vbnde\Docs\some: file.pdf"


def test_build_uses_local_date_for_created_and_iso8601_for_extracted_at(
    fixed_now, html_source
) -> None:
    """AC2 — `created` is YYYY-MM-DD; `extracted_at` is ISO 8601 with tz offset."""

    rendered = build(ExtractedMetadata(), html_source, fixed_now)
    parsed = yaml.safe_load(_strip_delimiters(rendered))

    assert parsed["created"] == "2026-04-18"
    # `extracted_at` is emitted as a string (datetime.isoformat()) so PyYAML
    # leaves it quoted; round-trip via fromisoformat to assert it parses back
    # to a tz-aware value identical to `fixed_now`.
    extracted_at_str = parsed["extracted_at"]
    assert isinstance(extracted_at_str, str)
    assert extracted_at_str == fixed_now.isoformat()
    parsed_dt = datetime.fromisoformat(extracted_at_str)
    assert parsed_dt == fixed_now
    assert parsed_dt.tzinfo is not None


def test_build_wraps_in_triple_dashes(fixed_now, html_source) -> None:
    """AC1 — output is delimited by `---` at both ends and ready to concat."""

    rendered = build(ExtractedMetadata(), html_source, fixed_now)

    lines = rendered.split("\n")
    assert lines[0] == "---"
    assert lines[-1] == "---"
    assert rendered.count("---") == 2


# ---- Story 1.7 — Partial-success frontmatter keys -------------------------


def test_build_emits_partial_and_failed_pages_when_partial_true(fixed_now, html_source) -> None:
    """AC4 — `partial: true` + ordered `failed_pages` appear after `generated_by`."""

    rendered = build(
        ExtractedMetadata(),
        html_source,
        fixed_now,
        partial_info=(True, [13, 14, 45]),
    )
    parsed = yaml.safe_load(_strip_delimiters(rendered))

    assert parsed["partial"] is True
    assert parsed["failed_pages"] == [13, 14, 45]

    # Key order matters for human-readability: integrity info MUST come right
    # after `generated_by` (arch §5.2) and BEFORE optional metadata.
    keys = list(parsed.keys())
    assert keys.index("partial") == keys.index("generated_by") + 1
    assert keys.index("failed_pages") == keys.index("partial") + 1


def test_build_omits_partial_keys_when_partial_false(fixed_now, html_source) -> None:
    """AC4 / FR4 — `partial: false` and `failed_pages: []` MUST NOT appear."""

    rendered = build(
        ExtractedMetadata(),
        html_source,
        fixed_now,
        partial_info=(False, []),
    )

    assert "partial:" not in rendered
    assert "failed_pages:" not in rendered


def test_build_defaults_match_clean_conversion(fixed_now, html_source) -> None:
    """Default `partial_info` MUST behave identically to `(False, [])`.

    This is the BC guard for callers that existed before Story 1.7 — they
    still pass only `(metadata, source, now)` and must continue to get the
    same output with no partial keys.
    """

    default_rendered = build(ExtractedMetadata(), html_source, fixed_now)
    explicit_rendered = build(
        ExtractedMetadata(),
        html_source,
        fixed_now,
        partial_info=(False, []),
    )

    assert default_rendered == explicit_rendered
