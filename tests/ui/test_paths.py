from pathlib import Path

from d4v.ui.paths import app_data_dir


def test_app_data_dir_uses_appdata(monkeypatch):
    monkeypatch.setenv("APPDATA", r"C:\Users\Tester\AppData\Roaming")
    path = app_data_dir()
    assert path == Path(r"C:\Users\Tester\AppData\Roaming") / "D4V"


def test_app_data_dir_falls_back_to_home(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    path = app_data_dir()
    assert path == tmp_path / ".d4v"
