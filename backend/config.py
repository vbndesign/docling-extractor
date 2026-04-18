"""Environment-driven configuration.

Settings are read from environment variables with sensible defaults for
local single-user usage. `get_settings()` is a FastAPI dependency; tests
override it via `app.dependency_overrides`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


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
