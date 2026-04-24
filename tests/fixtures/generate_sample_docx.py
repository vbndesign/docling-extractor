# ruff: noqa: E501 — OOXML XML templates must not be line-wrapped arbitrarily.
"""Regenerate ``tests/fixtures/sample.docx`` — Story 1.8 fixture.

Stdlib-only generator (no ``python-docx`` dev-dep). Produces a minimal
valid OOXML Word document with:

* title         — ``Docling DOCX Fixture`` (``dc:title``)
* author        — ``Test Author`` (``dc:creator``)
* created date  — ``2024-06-15T12:00:00Z`` (``dcterms:created`` → year 2024)
* body          — one visible paragraph

Run once (output committed); not a runtime / test dependency::

    python tests/fixtures/generate_sample_docx.py
"""

from __future__ import annotations

import zipfile
from pathlib import Path

OUTPUT = Path(__file__).parent / "sample.docx"

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
</Types>
"""

ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
</Relationships>
"""

CORE_PROPERTIES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
                   xmlns:dc="http://purl.org/dc/elements/1.1/"
                   xmlns:dcterms="http://purl.org/dc/terms/"
                   xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>Docling DOCX Fixture</dc:title>
  <dc:creator>Test Author</dc:creator>
  <dcterms:created xsi:type="dcterms:W3CDTF">2024-06-15T12:00:00Z</dcterms:created>
</cp:coreProperties>
"""

DOCUMENT_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p>
      <w:r>
        <w:t xml:space="preserve">This is a sample DOCX fixture used by the Story 1.8 suite. The body contains enough text to exceed the empty-markdown guard in docling_service.</w:t>
      </w:r>
    </w:p>
  </w:body>
</w:document>
"""


def main() -> None:
    with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", CONTENT_TYPES)
        zf.writestr("_rels/.rels", ROOT_RELS)
        zf.writestr("docProps/core.xml", CORE_PROPERTIES)
        zf.writestr("word/document.xml", DOCUMENT_XML)
    size_kb = OUTPUT.stat().st_size / 1024
    print(f"wrote {OUTPUT.name} ({size_kb:.2f} KB)")


if __name__ == "__main__":
    main()
