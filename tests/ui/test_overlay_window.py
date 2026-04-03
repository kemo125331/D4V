import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from d4v.overlay.config import OverlayConfig
from d4v.ui.overlay import OverlayWindow


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_apply_config_resets_auto_position_when_position_cleared():
    _app()
    window = OverlayWindow(config=OverlayConfig(position=(200, 300)))
    try:
        window._user_moved = True
        window.apply_config(OverlayConfig(position=None))
        assert window._user_moved is False
    finally:
        window.close()

