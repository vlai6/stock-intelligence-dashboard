"""Where scans, caches and alert state are stored.

Normal developer runs keep the legacy project-relative paths.  The Windows
launcher sets REGRESSION_SCANNER_DATA_DIR to a persistent user directory.
This keeps packaged assets read-only and data outside PyInstaller's bundle.
"""
from __future__ import annotations

import os
from pathlib import Path


def data_root() -> Path:
    configured = os.getenv("REGRESSION_SCANNER_DATA_DIR", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parent
