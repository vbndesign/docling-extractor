"""Generate the Story 1.7 ``large_text.pdf`` fixture.

Produces a deterministic, synthetic text-only PDF of ~104 pages plus a
``large_text.baseline.json`` sibling that records the ground-truth page
count and native text character count. The baseline file anchors AC2's
"≥ 90% of native-extractable characters" assertion: the test re-derives
native text via ``pypdfium2`` at run time and compares against the
committed number.

Why synthetic: the story's original trigger was a personal PDF of the
repo author, which must NOT be committed (privacy). The fixture uses
lorem-ipsum-style public-domain filler so the repo stays shareable.

Rerun only if the fixture is ever lost — the output is committed:

    python tests/fixtures/generate_large_pdf.py

Script is dev-only; ``reportlab`` sits in the ``[dev]`` optional extras.
"""

from __future__ import annotations

import json
from pathlib import Path

import pypdfium2 as pdfium
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

FIXTURE_DIR = Path(__file__).resolve().parent
OUTPUT_PDF = FIXTURE_DIR / "large_text.pdf"
BASELINE_JSON = FIXTURE_DIR / "large_text.baseline.json"

TARGET_PAGES = 104
LINES_PER_PAGE = 48
SEED_PARAGRAPH = (
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
    "Vestibulum condimentum, nibh vitae maximus vestibulum, nunc nisl "
    "aliquet odio, non viverra magna turpis eu orci. Pellentesque in "
    "libero vitae eros tempus commodo. Integer faucibus, leo a vehicula "
    "porttitor, lacus mi pharetra felis, id efficitur mauris arcu a leo."
)


def _line_text(page_idx: int, line_idx: int) -> str:
    """Deterministic line content.

    Including the 1-based page number in every line guarantees the
    concatenated markdown is easy to reason about ("page 42" appears 48
    times in the output), and keeps the baseline reproducible.
    """

    return f"P{page_idx + 1:04d}L{line_idx + 1:02d} {SEED_PARAGRAPH}"


def _native_text_chars(pdf_path: Path) -> int:
    """Sum of characters extractable via pypdfium2's text-page API.

    Story 1.7 AC2 defines the baseline as "total de caracteres extraíveis
    nativamente por pypdfium2 ... medido na fixture ao longo de
    ``get_textpage().get_text_range()`` por página". We measure here (at
    fixture-generation time) and commit the number so the test's 0.90
    ratio assertion has a fixed reference to compare against.
    """

    doc = pdfium.PdfDocument(pdf_path)
    try:
        total = 0
        for page in doc:
            text_page = page.get_textpage()
            try:
                length = text_page.count_chars()
                if length:
                    total += len(text_page.get_text_range(index=0, count=length))
            finally:
                text_page.close()
            page.close()
        return total
    finally:
        doc.close()


def generate() -> tuple[Path, Path]:
    """Write the fixture PDF + its baseline JSON and return both paths."""

    canvas_obj = canvas.Canvas(str(OUTPUT_PDF), pagesize=LETTER)
    canvas_obj.setFont("Helvetica", 10)

    for page_idx in range(TARGET_PAGES):
        y = 760
        for line_idx in range(LINES_PER_PAGE):
            line = _line_text(page_idx, line_idx)
            canvas_obj.drawString(48, y, line)
            y -= 14
        canvas_obj.showPage()

    canvas_obj.save()

    baseline = {
        "total_pages": TARGET_PAGES,
        "lines_per_page": LINES_PER_PAGE,
        "native_text_chars": _native_text_chars(OUTPUT_PDF),
        "seed": SEED_PARAGRAPH,
    }
    BASELINE_JSON.write_text(
        json.dumps(baseline, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    return OUTPUT_PDF, BASELINE_JSON


if __name__ == "__main__":
    pdf_path, baseline_path = generate()
    size_mb = pdf_path.stat().st_size / (1024 * 1024)
    data = json.loads(baseline_path.read_text(encoding="utf-8"))
    print(f"wrote {pdf_path} ({size_mb:.2f} MB, {data['total_pages']} pages)")
    print(f"wrote {baseline_path} (native_text_chars={data['native_text_chars']})")
