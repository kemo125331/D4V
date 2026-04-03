from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from d4v.ui.paths import app_data_dir


@dataclass
class UISettings:
    theme: str = "dark"
    font_scale: float = 1.0
    refresh_interval_ms: int = 50
    overlay_enabled: bool = True


def settings_path() -> Path:
    return app_data_dir() / "ui_settings.json"


def load_ui_settings(path: Path | None = None) -> UISettings:
    target = path or settings_path()
    if not target.exists():
        return UISettings()
    try:
        data = json.loads(target.read_text())
        return UISettings(**data)
    except (OSError, json.JSONDecodeError, TypeError):
        return UISettings()


def save_ui_settings(settings: UISettings, path: Path | None = None) -> None:
    target = path or settings_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(asdict(settings), indent=2))
