from types import SimpleNamespace

from d4v.overlay.view_model import MLModelInfo, PreviewViewModel
from d4v.ui.state import diagnostics_state_from_controller


def _controller(title: str = "D4V Live Preview"):
    return SimpleNamespace(
        window_title=title,
        elapsed_ms=95_000,
        view_model=lambda: PreviewViewModel(
            total_damage_label="0",
            rolling_dps_label="0",
            biggest_hit_label="0",
            last_hit_label="No hit yet",
            status_label="Ready",
            recent_hits=[],
            ml_model_info=MLModelInfo.detect_model(),
        ),
    )


def test_diagnostics_state_for_replay_controller():
    diagnostics = diagnostics_state_from_controller(_controller("D4V Replay Preview"))
    assert diagnostics.session_time_label == "01:35"
    assert diagnostics.game_focus_label == "Replay mode"
    assert diagnostics.window_binding_label == "Fixture session"
    assert diagnostics.runtime_mode_label == "Replay"


def test_diagnostics_state_for_live_controller(monkeypatch):
    monkeypatch.setattr("d4v.ui.state.is_diablo_iv_foreground", lambda: True)
    monkeypatch.setattr(
        "d4v.ui.state.get_diablo_iv_bounds",
        lambda: SimpleNamespace(width=1920, height=1080, left=100, top=50),
    )

    diagnostics = diagnostics_state_from_controller(_controller())
    assert diagnostics.session_time_label == "01:35"
    assert diagnostics.game_focus_label == "Focused"
    assert diagnostics.window_binding_label == "1920x1080 @ 100,50"
    assert diagnostics.runtime_mode_label == "Live"
