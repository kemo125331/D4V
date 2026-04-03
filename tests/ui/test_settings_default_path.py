from d4v.ui.settings import UISettings, load_ui_settings, save_ui_settings


def test_save_ui_settings_uses_appdata_default_path(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    settings = UISettings(overlay_enabled=False, refresh_interval_ms=75)
    save_ui_settings(settings)

    loaded = load_ui_settings()
    assert loaded.overlay_enabled is False
    assert loaded.refresh_interval_ms == 75
    assert (tmp_path / "D4V" / "ui_settings.json").exists()
