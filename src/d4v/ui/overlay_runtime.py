from __future__ import annotations

import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from d4v.overlay.game_overlay import GameOverlayController
from d4v.ui.overlay import OverlayWindow
from d4v.ui.state import overlay_view_model_from_controller


def run_overlay_runtime(controller: GameOverlayController | None = None) -> int:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv)

    overlay_controller = controller or GameOverlayController()
    overlay_controller.start()

    overlay = OverlayWindow()
    overlay.show()
    overlay.sync(overlay_view_model_from_controller(overlay_controller))

    timer = QTimer(overlay)

    def tick() -> None:
        overlay_controller.tick(100)
        overlay.sync(overlay_view_model_from_controller(overlay_controller))

    timer.timeout.connect(tick)
    timer.start(100)
    overlay.destroyed.connect(lambda: overlay_controller.stop())

    if owns_app:
        return app.exec()
    return 0
