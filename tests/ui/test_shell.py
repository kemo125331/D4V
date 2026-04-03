import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor, QCloseEvent
from PySide6.QtWidgets import QApplication

from d4v.overlay.view_model import MLModelInfo, PreviewViewModel
from d4v.ui.shell import MainShellWindow


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _controller():
    return SimpleNamespace(
        window_title="D4V Live Preview",
        session_name="test-session",
        start_button_label="Start Live",
        is_running=False,
        elapsed_ms=0,
        stop=lambda: None,
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


def test_close_event_runs_close_listeners():
    _app()
    window = MainShellWindow(_controller())
    calls: list[str] = []
    try:
        window.add_close_listener(lambda: calls.append("closed"))
        window.closeEvent(QCloseEvent())
        assert calls == ["closed"]
    finally:
        window.close()


def test_render_uses_model_status_color_for_hits_header():
    _app()
    controller = _controller()
    controller.view_model = lambda: PreviewViewModel(
        total_damage_label="0",
        rolling_dps_label="0",
        biggest_hit_label="0",
        last_hit_label="No hit yet",
        status_label="Ready",
        recent_hits=[],
        ml_model_info=MLModelInfo(
            is_custom=False,
            sample_count=0,
            session_count=0,
            status_color="orange",
        ),
    )
    window = MainShellWindow(controller)
    try:
        assert window._model_chip.text() == "Heuristic"
        assert window._hits_list.item(0).text() == "Waiting for hits"
        assert window._hits_list.item(0).foreground().color() == QColor("#7f8a9a")
    finally:
        window.close()


def test_overlay_controls_disable_when_overlay_hidden():
    _app()
    controller = _controller()
    window = MainShellWindow(controller)
    try:
        window._on_overlay_enabled_changed(False)
        assert window._click_through_checkbox.isEnabled() is False
        assert window._opacity_slider.isEnabled() is False
        assert window._overlay_mode_select.isEnabled() is False
    finally:
        window.close()


def test_overlay_controls_hidden_in_replay_mode():
    _app()
    controller = _controller()
    controller.window_title = "D4V Replay Preview"
    window = MainShellWindow(controller)
    try:
        assert window._overlay_card.isHidden() is True
    finally:
        window.close()
