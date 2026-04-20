"""Pure builder for the YAML frontmatter block.

`build(metadata, source, now)` returns a string already wrapped in ``---``
delimiters, ready to be concatenated with the markdown body. The function
is deterministic: callers pass a tz-aware ``now`` so tests assert exact
values without monkey-patching the clock.

AC2 mandatory keys: ``note_type``, ``created`` (YYYY-MM-DD), ``extracted_at``
(ISO 8601 with timezone), ``location``, ``generated_by``.

AC3 optional keys: ``source_title``, ``author``, ``year`` — emitted only when
the corresponding ``ExtractedMetadata`` field is populated. ``None`` values
are *omitted entirely* (no ``null``, no empty string, no placeholder).

AC4 forbidden keys (``title``, ``source_type``, ``domain``,
``concepts_extracted``) are never produced by this module.

Story 1.7 addition: ``partial_info=(True, (p1, p2, ...))`` inserts
``partial: true`` + ``failed_pages: [...]`` right after ``generated_by``.
When ``partial=False`` those keys are omitted entirely (FR4 / arch §5.2
"omissão > placeholder").
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

import yaml

from .models import ExtractedMetadata, SourceDescriptor

GENERATED_BY = "docling"
NOTE_TYPE = "literature_document"


def build(
    metadata: ExtractedMetadata,
    source: SourceDescriptor,
    now: datetime,
    *,
    partial_info: tuple[bool, Iterable[int]] = (False, ()),
) -> str:
    """Render the frontmatter block as a string wrapped in ``---`` delimiters.

    ``now`` MUST be tz-aware so that ``extracted_at`` carries an offset; this
    is the caller's responsibility (Story 1.4 wires it from a UTC-localized
    clock). The ``created`` field uses ``now.date()`` so it tracks the
    operator's local day.

    ``partial_info`` (Story 1.7) is a ``(partial, failed_pages)`` tuple.
    When ``partial=True``, the YAML carries ``partial: true`` + an ordered
    ``failed_pages`` list inserted **between** ``generated_by`` and the
    optional metadata keys so integrity information sits at the top of the
    file (most useful diagnostic when opening a generated ``.md``).
    """

    payload: dict[str, Any] = {
        "note_type": NOTE_TYPE,
        "created": now.date().isoformat(),
        "extracted_at": now.isoformat(),
        "location": source.location,
        "generated_by": GENERATED_BY,
    }

    partial, failed_pages = partial_info
    if partial:
        payload["partial"] = True
        payload["failed_pages"] = list(failed_pages)

    if metadata.source_title is not None:
        payload["source_title"] = metadata.source_title
    if metadata.author is not None:
        payload["author"] = metadata.author
    if metadata.year is not None:
        payload["year"] = metadata.year

    yaml_block = yaml.safe_dump(
        payload,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )

    return f"---\n{yaml_block}---"
