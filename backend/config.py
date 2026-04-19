"""Environment-driven configuration.

Settings are read from environment variables with sensible defaults for
local single-user usage. `get_settings()` is a FastAPI dependency; tests
override it via `app.dependency_overrides`.

The project `.env` (at repo root) is auto-loaded at import time so local
users can tune `OUTPUT_DIR` / `MAX_UPLOAD_MB` / `REQUEST_TIMEOUT_SECONDS`
without having to export shell variables. Existing env vars win over
`.env` (load_dotenv default: ``override=False``).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


@dataclass(frozen=True)
class Settings:
    output_dir: Path
    max_upload_mb: int
    request_timeout_seconds: int


def _load_settings() -> Settings:
    return Settings(
        output_dir=Path(os.environ.get("OUTPUT_DIR", "./output")),
        max_upload_mb=int(os.environ.get("MAX_UPLOAD_MB", "50")),
        request_timeout_seconds=int(os.environ.get("REQUEST_TIMEOUT_SECONDS", "60")),
    )


def get_settings() -> Settings:
    return _load_settings()
