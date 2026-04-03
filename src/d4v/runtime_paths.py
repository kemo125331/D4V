from __future__ import annotations

import sys
from pathlib import Path

from d4v.ui.paths import app_data_dir


def bundle_root() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return Path(__file__).resolve().parents[2]


def bundled_models_dir() -> Path:
    return bundle_root() / "models"


def bundled_docs_dir() -> Path:
    return bundle_root() / "docs"


def replay_sessions_dir() -> Path:
    return app_data_dir() / "replays"
