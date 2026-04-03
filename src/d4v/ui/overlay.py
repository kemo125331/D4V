from __future__ import annotations

import ctypes

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFont, QMouseEvent
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget

from d4v.capture.game_window import get_diablo_iv_bounds
from d4v.overlay.config import OverlayConfig, load_overlay_config, save_overlay_config
from d4v.overlay.game_overlay import GameOverlayViewModel
from d4v.ui.state import MainWindowState


GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020


class OverlayWindow(QWidget):
    def __init__(self, config: OverlayConfig | None = None) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.config = config or load_overlay_config()
        self._click_through_enabled = False
        self._user_moved = False
        self._drag_offset: tuple[int, int] | None = None

        self._avg_value = QLabel("0")
        self._last_value = QLabel("--")
        self._dps_value = QLabel("0")
        self._total_value = QLabel("0")
        self._hits_value = QLabel("0")
        self._peak_value = QLabel("0")
        self._time_value = QLabel("00:00")
        self._grid: QGridLayout | None = None

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus, True)

        self._build_ui()
        self._update_position()

    def _build_ui(self) -> None:
        self.resize(280, 190)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        card = QFrame(self)
        card.setObjectName("overlayCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(8)

        title = QLabel("D4V Combat")
        title.setStyleSheet(f"color: {self.config.title_color};")
        title.setFont(QFont(self.config.font_family, 9, QFont.Weight.Bold))
        card_layout.addWidget(title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(4)
        self._grid = grid
        card_layout.addLayout(grid)
        self._rebuild_rows()

        outer.addWidget(card)
        self.setStyleSheet(
            f"""
            QFrame#overlayCard {{
                background: rgba(26, 26, 26, {self._alpha_channel_value()});
                border: 1px solid {self.config.separator_color};
                border-radius: 12px;
            }}
            QLabel {{
                color: #ffffff;
            }}
            """
        )

    def _rebuild_rows(self) -> None:
        if self._grid is None:
            return
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        rows = [
            (
                "AVG DMG",
                self._avg_value,
                self.config.text_color,
                self.config.font_size + 4,
            ),
            ("LAST DMG", self._last_value, "#ffff00", self.config.font_size + 4),
        ]
        if self.config.mode == "expanded":
            rows.extend(
                [
                    (
                        "PEAK",
                        self._peak_value,
                        "#ffffff",
                        max(self.config.font_size - 1, 11),
                    ),
                    (
                        "TIME",
                        self._time_value,
                        "#ffffff",
                        max(self.config.font_size - 1, 11),
                    ),
                    (
                        "DPS",
                        self._dps_value,
                        "#ffffff",
                        max(self.config.font_size - 1, 11),
                    ),
                    (
                        "TOTAL",
                        self._total_value,
                        "#ffffff",
                        max(self.config.font_size - 1, 11),
                    ),
                    (
                        "HITS",
                        self._hits_value,
                        "#ffffff",
                        max(self.config.font_size - 1, 11),
                    ),
                ]
            )
        else:
            rows.extend(
                [
                    (
                        "DPS",
                        self._dps_value,
                        "#ffffff",
                        max(self.config.font_size - 1, 11),
                    ),
                    (
                        "PEAK",
                        self._peak_value,
                        "#ffffff",
                        max(self.config.font_size - 1, 11),
                    ),
                ]
            )

        for index, (label, value, color, size) in enumerate(rows):
            self._add_row(self._grid, index, label, value, color, size)

        self.resize(280, 220 if self.config.mode == "expanded" else 150)

    def _add_row(
        self,
        grid: QGridLayout,
        row: int,
        label_text: str,
        value: QLabel,
        color: str,
        size: int,
    ) -> None:
        label = QLabel(label_text)
        label.setStyleSheet(f"color: {self.config.label_color};")
        label.setFont(QFont(self.config.font_family, 9))
        grid.addWidget(label, row, 0)

        value.setStyleSheet(f"color: {color};")
        value.setFont(
            QFont(
                self.config.font_family,
                size,
                QFont.Weight.Bold if row < 2 else QFont.Weight.Medium,
            )
        )
        value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        grid.addWidget(value, row, 1)

    def _alpha_channel_value(self) -> int:
        return max(40, min(int(self.config.opacity * 255), 255))

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        if self.config.click_through:
            QTimer.singleShot(100, self._enable_click_through)

    def _enable_click_through(self) -> None:
        try:
            hwnd = int(self.winId())
            ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ex_style |= WS_EX_LAYERED | WS_EX_TRANSPARENT
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)
            self._click_through_enabled = True
        except (AttributeError, OSError):
            self._click_through_enabled = False

    def _disable_click_through(self) -> None:
        try:
            hwnd = int(self.winId())
            ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ex_style &= ~WS_EX_TRANSPARENT
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)
            self._click_through_enabled = False
        except (AttributeError, OSError):
            self._click_through_enabled = False

    def sync(self, view_model: GameOverlayViewModel) -> None:
        self._avg_value.setText(view_model.avg_damage_label)
        self._last_value.setText(view_model.last_damage_label)
        self._dps_value.setText(view_model.dps_label)
        self._total_value.setText(view_model.total_damage_label)
        self._hits_value.setText(view_model.hits_count_label)
        self._peak_value.setText(view_model.peak_hit_label)
        self._time_value.setText(view_model.session_time_label)
        if not self._user_moved:
            self._update_position()

    def sync_from_state(self, state: MainWindowState, controller: object) -> None:
        del state
        from d4v.ui.state import overlay_view_model_from_controller

        self.sync(overlay_view_model_from_controller(controller))

    def apply_config(self, config: OverlayConfig) -> None:
        should_reset_auto_position = (
            self.config.position is not None and config.position is None
        )
        self.config = config
        if should_reset_auto_position:
            self._user_moved = False
        self.setStyleSheet(
            f"""
            QFrame#overlayCard {{
                background: rgba(26, 26, 26, {self._alpha_channel_value()});
                border: 1px solid {self.config.separator_color};
                border-radius: 12px;
            }}
            QLabel {{
                color: #ffffff;
            }}
            """
        )
        self._rebuild_rows()
        self._update_position()
        if self.config.click_through:
            QTimer.singleShot(50, self._enable_click_through)
        else:
            self._disable_click_through()

    def reset_position(self) -> None:
        self._user_moved = False
        self.config.position = None
        save_overlay_config(self.config)
        self._update_position()

    def _update_position(self) -> None:
        if self.config.position is not None:
            x, y = self.config.position
            self.move(x, y)
            return

        bounds = get_diablo_iv_bounds()
        if bounds is None:
            screen = self.screen()
            if screen is None:
                return
            geometry = screen.availableGeometry()
            self.move(20, geometry.height() - 220)
            return

        self.move(bounds.left + 20, bounds.top + bounds.height - 220)

    def _save_position(self) -> None:
        self.config.position = (self.x(), self.y())
        save_overlay_config(self.config)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            if self._click_through_enabled:
                self._disable_click_through()
            global_pos = event.globalPosition().toPoint()
            self._drag_offset = (global_pos.x() - self.x(), global_pos.y() - self.y())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if self._drag_offset is not None:
            global_pos = event.globalPosition().toPoint()
            self.move(
                global_pos.x() - self._drag_offset[0],
                global_pos.y() - self._drag_offset[1],
            )
            self._user_moved = True
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._drag_offset is not None
        ):
            self._drag_offset = None
            self._save_position()
            if self.config.click_through:
                QTimer.singleShot(300, self._enable_click_through)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self._user_moved:
            self._save_position()
        super().closeEvent(event)
