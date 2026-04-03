from pathlib import Path

from d4v.runtime_paths import bundle_root, bundled_models_dir, replay_sessions_dir


def test_bundle_root_defaults_to_repo_root():
    assert bundle_root() == Path(__file__).resolve().parents[2]


def test_bundled_models_dir_points_to_models():
    assert bundled_models_dir() == bundle_root() / "models"


def test_replay_sessions_dir_uses_appdata(monkeypatch):
    monkeypatch.setenv("APPDATA", r"C:\Users\Tester\AppData\Roaming")
    assert replay_sessions_dir() == Path(r"C:\Users\Tester\AppData\Roaming") / "D4V" / "replays"
