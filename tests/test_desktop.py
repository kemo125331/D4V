from d4v.desktop import main


def test_desktop_main_launches_live_preview_with_overlay(monkeypatch):
    calls: list[str] = []

    monkeypatch.setattr(
        "d4v.desktop.main_live_with_overlay",
        lambda: calls.append("desktop") or 0,
    )

    assert main() == 0
    assert calls == ["desktop"]
