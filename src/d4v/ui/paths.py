from __future__ import annotations

import os
from pathlib import Path


APP_DIR_NAME = "D4V"


def app_data_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / APP_DIR_NAME
    return Path.home() / ".d4v"
