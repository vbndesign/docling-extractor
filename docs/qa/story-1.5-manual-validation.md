# Story 1.5 — Manual Validation Checklist

> **Scope:** Story 1.5 AC9 — manual browser validation of the HTMX frontend.
> **Status:** Ready for operator execution.
> **Pre-requisites:**
> - Backend running via `uv run uvicorn backend.main:app --host 127.0.0.1 --port 8000`
> - First boot may take 2–5 min (Docling model download). Wait for `Application startup complete.`
> - A real, publicly-reachable HTML article URL.
> - A real, publicly-reachable PDF URL.
> - A local `.pdf` file on disk (keep the absolute path handy).
> - A known-bad URL that returns HTTP 404.

Open `http://127.0.0.1:8000` for every scenario below.

## Chrome

- [ ] **URL (HTML article)** — paste URL, click Extract. Expect `result-card--success` with absolute path, `Copy Path` works (button text flips to "Copied!" for ~1.5s).
- [ ] **URL (remote PDF)** — paste PDF URL, click Extract. Expect `result-card--success`.
- [ ] **Drag-and-drop PDF** — drop local `.pdf` onto the dropzone. Expect `is-dragging` highlight on dragover; processing card shows "Ingestion Active"; success card follows.
- [ ] **Browse PDF (click to upload)** — click the dropzone, pick a PDF in the dialog. Same success result.
- [ ] **local_path fallback** — paste absolute path (e.g. `C:\path\to\paper.pdf`) into the fallback field, click Extract. Expect success card in the same `#result` area.
- [ ] **Error — URL 404** — paste known-404 URL. Expect `result-card--error` with code `SOURCE_FETCH_FAILED`, message, and non-empty hint. No popup/toast.
- [ ] **`New Ingest` link** — after a success, clicking it reloads the page and returns the empty-state.
- [ ] **System Health pill** — loads as green `SERVICE_ACTIVE` after `DOMContentLoaded`; flips to red `SERVICE_DOWN` if you stop the server and reload.
- [ ] **Output Dir** — header shows the configured `OUTPUT_DIR` value.
- [ ] **Processing indicator** — visible (spinner + "Ingestion Active") only during extraction; hidden otherwise.

## Keyboard-only (Chrome) — added by UX gate v1.3

- [ ] **Tab sequence** — from page load, Tab lands on: URL input → Extract btn → dropzone → path input → Extract btn → Copy Path (after success) → New Ingest. Focus indicator visible on every stop (outline on buttons/links, border-accent on inputs). Hidden file input MUST be skipped.
- [ ] **Submit via keyboard** — Tab to URL input → type → Tab to Extract → Enter. Result area updates; screen reader (if enabled) announces via `aria-live="polite"`.
- [ ] **Dropzone via keyboard** — Tab to dropzone (visible focus ring) → Enter → native file picker opens → choose PDF → submission auto-fires.

## Firefox

(Sanity pass — repeat the 4 success paths in Firefox.)

- [ ] URL (HTML article) success.
- [ ] URL (remote PDF) success.
- [ ] Drag-and-drop PDF success.
- [ ] local_path fallback success.

## Artifacts

- Record each `output_path` returned into the validation log.
- If any card or state fails, attach a screenshot and console output.
