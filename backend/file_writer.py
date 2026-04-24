"""Persist the extracted document to disk.

`save(frontmatter_str, markdown_body, metadata, source, output_dir, *, now)`
concatenates the frontmatter and markdown, derives a deterministic
filename, applies kebab-case slugification, and writes the result
atomically — appending an incremental suffix (``-2``, ``-3`` …) on
collision rather than overwriting an existing file (AC7 + arch §2.2 R6).

Filename derivation priority (FR7 / arch §5.1):

1. ``metadata.source_title`` when non-empty after ``.strip()``.
2. The stem of ``source.original_filename`` for file sources
   (``pdf_upload``, ``pdf_local_path``, ``docx_upload``,
   ``docx_local_path``). ``Path.stem`` strips whatever extension was on
   the original file, so both ``briefing.docx`` and ``paper.pdf`` land
   on a ``.md`` name cleanly — never ``briefing.docx.md``.
3. A slug derived from the URL (``source.location``): the last
   non-empty path segment, falling back to the host.

Edge cases:

- arch §2.2 R5 — slug truncated to 200 chars *before* adding the
  collision suffix and ``.md`` extension; keeps total well under the
  NTFS 255-char limit.
- arch §2.2 R9 — when slugification yields an empty string (e.g. CJK or
  pure-symbol titles) the fallback ``document-{timestamp}`` is used.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from slugify import slugify

from .models import ExtractedMetadata, SaveResult, SourceDescriptor

SLUG_MAX_LENGTH = 200
EXTENSION = ".md"
FILE_SOURCE_KINDS = frozenset({"pdf_upload", "pdf_local_path", "docx_upload", "docx_local_path"})


def _slug_from_url(location: str) -> str:
    """Pick the most descriptive segment of a URL for filename derivation."""

    parsed = urlparse(location)
    if parsed.path:
        segments = [seg for seg in parsed.path.split("/") if seg]
        if segments:
            return segments[-1]
    if parsed.netloc:
        return parsed.netloc
    return location


def _raw_basename(metadata: ExtractedMetadata, source: SourceDescriptor) -> str:
    """Pick the raw (un-slugified) string that drives the filename."""

    if metadata.source_title is not None:
        title = metadata.source_title.strip()
        if title:
            return title

    if source.kind in FILE_SOURCE_KINDS and source.original_filename:
        stem = Path(source.original_filename).stem
        if stem:
            return stem

    return _slug_from_url(source.location)


def _resolve_now(now: datetime | None) -> datetime:
    return now if now is not None else datetime.now(tz=UTC)


def _derive_slug(
    metadata: ExtractedMetadata,
    source: SourceDescriptor,
    now: datetime,
) -> str:
    """Return the kebab-case slug used as the filename base (no extension)."""

    raw = _raw_basename(metadata, source)
    slug = slugify(raw, separator="-", lowercase=True, max_length=SLUG_MAX_LENGTH)
    if slug:
        return slug
    return f"document-{int(now.timestamp())}"


def save(
    frontmatter_str: str,
    markdown_body: str,
    metadata: ExtractedMetadata,
    source: SourceDescriptor,
    output_dir: Path,
    *,
    now: datetime | None = None,
) -> SaveResult:
    """Write the rendered document and return the resolved path + basename.

    ``output_dir`` is created if missing. ``now`` is exposed as a keyword
    argument so the empty-slug fallback (R9) is deterministic in tests; it
    defaults to ``datetime.now(tz=UTC)`` for production callers.
    """

    output_dir.mkdir(parents=True, exist_ok=True)

    base = _derive_slug(metadata, source, _resolve_now(now))
    content = frontmatter_str + "\n" + markdown_body

    counter = 1
    while True:
        filename = f"{base}{EXTENSION}" if counter == 1 else f"{base}-{counter}{EXTENSION}"
        candidate = output_dir / filename
        try:
            with candidate.open("x", encoding="utf-8") as handle:
                handle.write(content)
        except FileExistsError:
            counter += 1
            continue
        return SaveResult(output_path=candidate.resolve(), filename=candidate.name)
