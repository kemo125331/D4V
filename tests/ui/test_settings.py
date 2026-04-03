import json
from pathlib import Path

from d4v.ui.settings import UISettings, load_ui_settings, save_ui_settings


def test_load_ui_settings_returns_defaults_for_missing_file(tmp_path: Path):
    path = tmp_path / "missing.json"
    settings = load_ui_settings(path)
    assert settings == UISettings()


def test_save_and_load_ui_settings_round_trip(tmp_path: Path):
    path = tmp_path / "ui_settings.json"
    original = UISettings(
        theme="dark",
        font_scale=1.2,
        refresh_interval_ms=100,
        overlay_enabled=False,
    )

    save_ui_settings(original, path)

    raw = json.loads(path.read_text())
    assert raw["font_scale"] == 1.2
    assert raw["refresh_interval_ms"] == 100

    loaded = load_ui_settings(path)
    assert loaded == original
