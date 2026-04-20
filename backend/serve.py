from __future__ import annotations

import sys
import threading
import time
import webbrowser

import uvicorn

_HOST = "127.0.0.1"
_PORT = 8000
_URL = f"http://{_HOST}:{_PORT}"


def _open_browser_when_ready() -> None:
    time.sleep(1.2)
    webbrowser.open(_URL)


def main() -> None:
    reload = "--reload" in sys.argv[1:]
    threading.Thread(target=_open_browser_when_ready, daemon=True).start()
    suffix = " (--reload)" if reload else ""
    print(f"Docling Extractor starting on {_URL}{suffix}")
    uvicorn.run("backend.main:app", host=_HOST, port=_PORT, reload=reload)


if __name__ == "__main__":
    main()
