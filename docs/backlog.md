# Docling Extractor — Backlog

Unscoped enhancements, technical debt, and bugs. Items live here until they are promoted into an epic and drafted as a numbered story in `docs/stories/`. The PO prioritizes; the PM decides epic placement.

## Legend

- **Type:** 🔧 T = Technical Debt · ✨ E = Enhancement · 🐛 B = Bug
- **Priority:** 🔴 Critical · 🟠 High · 🟡 Medium · 🟢 Low

---

## Enhancements

### E-001 · GPU acceleration (CUDA) for Docling pipeline

| Field | Value |
|---|---|
| **Type** | ✨ Enhancement |
| **Priority** | 🟡 Medium |
| **Related Story** | Epic 1 (post-MVP) |
| **Impact Area** | `backend/docling_service.py`, `backend/config.py`, `pyproject.toml` |
| **Tags** | performance, docling, cuda, nvidia |
| **Estimated Effort** | 1–2 days |
| **Created** | 2026-04-19 by @dev (Dex) |

**Context:** Operator tested a 100-page PDF successfully after fixing `.env` loading (Story 1.1 hotfix v1.5), but extraction still takes close to the 300s timeout on CPU. Docling supports GPU acceleration via torch+CUDA for layout analysis and OCR, typically giving a 5–10× speedup on OCR-heavy PDFs.

**Problem:** The current `DocumentConverter` in `backend/docling_service.py` uses default accelerator settings (CPU). There is no env toggle, no runtime CUDA detection, and no fallback path if a user installs torch+CUDA but the GPU isn't available at runtime.

**Proposed work:**
- Introduce env `DOCLING_ACCELERATOR` (`auto` | `cuda` | `cpu`, default `auto`).
- Runtime detection: `torch.cuda.is_available()` → select device; on `auto` pick GPU if present, fall back to CPU with a log line.
- Wire the selected device into Docling's `AcceleratorOptions` when building the pipeline.
- Document GPU setup in `README.md` (NVIDIA driver + CUDA-enabled torch install, wheel URL).
- Keep the default install CPU-only — GPU torch is opt-in via an extras group (e.g. `uv sync --extra gpu`).

**Constraints / risks:**
- Torch+CUDA adds ~2GB to the venv; must stay optional.
- First-run still pays model download cost.
- Needs a smoke test matrix: CPU-only box vs NVIDIA box.

**Acceptance criteria sketch (for the future story):**
1. `DOCLING_ACCELERATOR` env honored; `.env.example` documents all three values.
2. CPU path unchanged behaviorally when GPU is absent.
3. When GPU is selected, `/health` or a new `/info` surface exposes the active accelerator so the operator can confirm.
4. 100-page PDF benchmark: CPU baseline vs GPU result documented.

---

## Technical Debt

*(none yet)*

---

## Change Log

| Date | Item | Event | Author |
|---|---|---|---|
| 2026-04-19 | E-001 | Registered from hotfix conversation after successful 100-page extraction on CPU @ 300s timeout. | Dex (@dev) |
