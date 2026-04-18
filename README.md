# Docling Extractor

Local, single-user tool that converts URLs (HTML/PDF) and PDF uploads into
Markdown files ready for ingestion into an Obsidian vault. Built on
[Docling](https://github.com/docling-project/docling) and FastAPI.

> Status: Story 1.1 scaffolding — only `GET /health` is wired up.

## Prerequisites

- Python **3.11 or newer**
- `pip` (or [`uv`](https://github.com/astral-sh/uv) — preferred if you have it)
- ~2 GB free disk space for the Docling model cache (downloaded on first
  conversion, not during this story)

## Installation

Clone the repo, create a virtual environment, and install the project in
editable mode with dev extras:

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate

pip install -e ".[dev]"
```

Or with `uv`:

```bash
uv venv
uv pip install -e ".[dev]"
```

## Configuration

Copy `.env.example` to `.env` and adjust if needed. The variables used by
this project are:

| Variable                   | Default     | Description                                 |
| -------------------------- | ----------- | ------------------------------------------- |
| `OUTPUT_DIR`               | `./output`  | Where converted `.md` files land            |
| `MAX_UPLOAD_MB`            | `50`        | Max PDF upload size                         |
| `REQUEST_TIMEOUT_SECONDS`  | `60`        | Timeout for outbound fetches and `/extract` |

## Running the server

From the project root:

```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

The server binds to `127.0.0.1` by default (localhost only). To expose it
on your LAN, pass `--host 0.0.0.0` explicitly — but note this tool has no
authentication, so only do that on a trusted network.

## Health check

With the server running:

```bash
curl http://127.0.0.1:8000/health
# → {"status":"ok"}
```

Or open <http://127.0.0.1:8000/health> in a browser.

## Project layout

```
backend/      FastAPI app, services, file writer (incrementally filled by stories 1.2+)
frontend/     Jinja2 templates + static assets (story 1.5)
tests/        pytest suite (story 1.2+)
output/       gitignored — your generated Markdown files
```

## License

MIT.
