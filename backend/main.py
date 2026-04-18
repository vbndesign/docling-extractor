"""FastAPI application entry point."""

from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="Docling Extractor", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
