from __future__ import annotations

import sys
from collections.abc import Callable

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from d4v.overlay.config import OverlayConfig, load_overlay_config, save_overlay_config
from d4v.ui.settings import UISettings, load_ui_settings
from d4v.ui.state import MainWindowState


class MainShellWindow(QMainWindow):
    def __init__(self, controller: object, settings: UISettings | None = None) -> None:
        super().__init__()
        self.controller = controller
        self.settings = settings or load_ui_settings()
        self.overlay_config = load_overlay_config()
        self._render_listeners: list[Callable[[MainWindowState], None]] = []
        self._overlay_config_listeners: list[Callable[[OverlayConfig], None]] = []
        self._overlay_enabled_listeners: list[Callable[[bool], None]] = []
        self._close_listeners: list[Callable[[], None]] = []
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

        self._title_label = QLabel()
        self._session_chip = QLabel()
        self._status_chip = QLabel()
        self._status_label = QLabel()
        self._timer_chip = QLabel()
        self._focus_chip = QLabel()
        self._mode_chip = QLabel()
        self._model_chip = QLabel()
        self._total_value = QLabel()
        self._dps_value = QLabel()
        self._biggest_value = QLabel()
        self._last_value = QLabel()
        self._hits_list = QListWidget()
        self._start_button = QPushButton()
        self._stop_button = QPushButton("Stop")
        self._reset_button = QPushButton("Reset")
        self._overlay_enabled_checkbox = QCheckBox("Show overlay")
        self._click_through_checkbox = QCheckBox("Click-through")
        self._opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._opacity_value = QLabel()
        self._overlay_mode_select = QComboBox()
        self._reset_overlay_position_button = QPushButton("Reset Position")
        self._overlay_card = QFrame()

        self._build_ui()
        self._render()

    def _build_ui(self) -> None:
        self.setWindowTitle(
            str(getattr(self.controller, "window_title", "D4V Preview"))
        )
        self.resize(760, 560)

        central = QWidget(self)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(14)

        hero_card = self._card("")
        hero_layout = hero_card.layout()
        assert isinstance(hero_layout, QVBoxLayout)
        hero_layout.setSpacing(12)

        hero_top = QHBoxLayout()
        hero_top.setSpacing(10)
        self._title_label.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        hero_top.addWidget(self._title_label)
        hero_top.addStretch(1)
        hero_top.addWidget(self._status_chip)
        hero_layout.addLayout(hero_top)

        chips_row = QHBoxLayout()
        chips_row.setSpacing(8)
        chips_row.addWidget(self._session_chip)
        chips_row.addWidget(self._mode_chip)
        chips_row.addWidget(self._focus_chip)
        chips_row.addWidget(self._timer_chip)
        chips_row.addWidget(self._model_chip)
        chips_row.addStretch(1)
        hero_layout.addLayout(chips_row)

        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet("color: #a9b1ba;")
        hero_layout.addWidget(self._status_label)
        outer.addWidget(hero_card)

        metrics_grid = QHBoxLayout()
        metrics_grid.setSpacing(12)
        metrics_grid.addWidget(self._metric_card("TOTAL", self._total_value))
        metrics_grid.addWidget(self._metric_card("DPS", self._dps_value))
        metrics_grid.addWidget(self._metric_card("PEAK", self._biggest_value))
        metrics_grid.addWidget(self._metric_card("LAST", self._last_value))
        outer.addLayout(metrics_grid)

        controls = QHBoxLayout()
        controls.setSpacing(10)
        self._start_button.clicked.connect(self.start)
        self._stop_button.clicked.connect(self.stop)
        self._reset_button.clicked.connect(self.reset)
        controls.addWidget(self._start_button)
        controls.addWidget(self._stop_button)
        controls.addWidget(self._reset_button)
        controls.addStretch(1)
        outer.addLayout(controls)

        log_card = self._card("Hits")
        log_layout = log_card.layout()
        assert isinstance(log_layout, QVBoxLayout)
        self._hits_list.setAlternatingRowColors(True)
        log_layout.addWidget(self._hits_list)
        outer.addWidget(log_card, stretch=1)

        self._overlay_card = self._card("Overlay")
        overlay_layout = self._overlay_card.layout()
        assert isinstance(overlay_layout, QVBoxLayout)

        overlay_toggles = QHBoxLayout()
        self._overlay_enabled_checkbox.setChecked(self.settings.overlay_enabled)
        self._click_through_checkbox.setChecked(self.overlay_config.click_through)
        self._overlay_enabled_checkbox.toggled.connect(self._on_overlay_enabled_changed)
        self._click_through_checkbox.toggled.connect(self._on_click_through_changed)
        overlay_toggles.addWidget(self._overlay_enabled_checkbox)
        overlay_toggles.addWidget(self._click_through_checkbox)
        overlay_toggles.addStretch(1)
        overlay_layout.addLayout(overlay_toggles)

        opacity_row = QHBoxLayout()
        opacity_label = QLabel("Opacity")
        opacity_label.setStyleSheet("color: #8b949e;")
        self._opacity_slider.setRange(25, 100)
        self._opacity_slider.setValue(int(self.overlay_config.opacity * 100))
        self._opacity_slider.valueChanged.connect(self._on_opacity_changed)
        self._opacity_value.setMinimumWidth(42)
        opacity_row.addWidget(opacity_label)
        opacity_row.addWidget(self._opacity_slider, stretch=1)
        opacity_row.addWidget(self._opacity_value)
        overlay_layout.addLayout(opacity_row)

        mode_row = QHBoxLayout()
        mode_label = QLabel("Mode")
        mode_label.setStyleSheet("color: #8b949e;")
        self._overlay_mode_select.addItems(["expanded", "compact"])
        self._overlay_mode_select.setCurrentText(self.overlay_config.mode)
        self._overlay_mode_select.currentTextChanged.connect(
            self._on_overlay_mode_changed
        )
        mode_row.addWidget(mode_label)
        mode_row.addWidget(self._overlay_mode_select)
        mode_row.addStretch(1)
        overlay_layout.addLayout(mode_row)

        self._reset_overlay_position_button.clicked.connect(
            self._on_reset_overlay_position
        )
        overlay_layout.addWidget(self._reset_overlay_position_button)

        outer.addWidget(self._overlay_card)

        self._apply_theme()
        self._sync_overlay_controls()
        self.setCentralWidget(central)

    def _card(self, title: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        label = QLabel(title)
        label.setStyleSheet("color: #8b949e; font-weight: 600;")
        layout.addWidget(label)
        return frame

    def _metric_card(self, title: str, value_label: QLabel) -> QFrame:
        card = self._card(title)
        layout = card.layout()
        assert isinstance(layout, QVBoxLayout)
        value_label.setFont(
            QFont("Segoe UI", int(20 * self.settings.font_scale), QFont.Weight.Bold)
        )
        layout.addWidget(value_label)
        return card

    def _apply_theme(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background: #0b0d12;
            }
            QLabel {
                color: #f5f7fa;
            }
            QFrame#card {
                background: #141821;
                border: 1px solid #202634;
                border-radius: 12px;
            }
            QListWidget {
                background: #10141c;
                border: 1px solid #202634;
                border-radius: 8px;
                color: #e5e7eb;
                padding: 6px;
            }
            QPushButton {
                background: #14746f;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 9px 15px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #19958e;
            }
            QPushButton:disabled {
                background: #394150;
                color: #9aa4b2;
            }
            QComboBox, QSlider, QCheckBox {
                color: #f5f7fa;
            }
            QComboBox {
                background: #10141c;
                border: 1px solid #202634;
                border-radius: 8px;
                padding: 6px 10px;
            }
            QCheckBox {
                color: #f5f7fa;
            }
            QSlider::groove:horizontal {
                background: #202634;
                height: 6px;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #14746f;
                width: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }
            """
        )

    def _sync_overlay_controls(self) -> None:
        self._opacity_value.setText(f"{int(self.overlay_config.opacity * 100)}%")
        advanced_enabled = self.settings.overlay_enabled and self._overlay_card.isVisible()
        self._click_through_checkbox.setEnabled(advanced_enabled)
        self._opacity_slider.setEnabled(advanced_enabled)
        self._overlay_mode_select.setEnabled(advanced_enabled)
        self._reset_overlay_position_button.setEnabled(advanced_enabled)

    def _chip_style(self, background: str, text: str = "#f5f7fa") -> str:
        return (
            f"background: {background}; color: {text}; border-radius: 999px; "
            "padding: 4px 10px; font-weight: 600;"
        )

    def _model_summary_text(self, state: MainWindowState) -> str:
        info = state.metrics.ml_model_info
        if info.is_custom:
            return "Custom ML"
        if info.sample_count > 0:
            return "Bundled ML"
        return "Heuristic"

    def _status_chip_style(self, status_text: str, is_running: bool) -> str:
        lowered = status_text.lower()
        if "error" in lowered:
            return self._chip_style("#7f1d1d")
        if "paused" in lowered or "background" in lowered:
            return self._chip_style("#7c5c12")
        if is_running:
            return self._chip_style("#14532d")
        return self._chip_style("#263041")

    def _notify_overlay_config_changed(self) -> None:
        for listener in self._overlay_config_listeners:
            listener(self.overlay_config)

    def _notify_overlay_enabled_changed(self) -> None:
        for listener in self._overlay_enabled_listeners:
            listener(self.settings.overlay_enabled)

    def _on_overlay_enabled_changed(self, checked: bool) -> None:
        self.settings.overlay_enabled = checked
        from d4v.ui.settings import save_ui_settings

        save_ui_settings(self.settings)
        self._sync_overlay_controls()
        self._notify_overlay_enabled_changed()

    def _on_click_through_changed(self, checked: bool) -> None:
        self.overlay_config.click_through = checked
        save_overlay_config(self.overlay_config)
        self._notify_overlay_config_changed()

    def _on_opacity_changed(self, value: int) -> None:
        self.overlay_config.opacity = value / 100.0
        save_overlay_config(self.overlay_config)
        self._sync_overlay_controls()
        self._notify_overlay_config_changed()

    def _on_reset_overlay_position(self) -> None:
        self.overlay_config.position = None
        save_overlay_config(self.overlay_config)
        self._notify_overlay_config_changed()

    def _on_overlay_mode_changed(self, value: str) -> None:
        self.overlay_config.mode = value
        save_overlay_config(self.overlay_config)
        self._notify_overlay_config_changed()

    def start(self) -> None:
        self.controller.start()
        self._timer.start(self.settings.refresh_interval_ms)
        self._render()

    def stop(self) -> None:
        self.controller.stop()
        self._timer.stop()
        self._render()

    def reset(self) -> None:
        self.controller.reset()
        self._render()

    def _tick(self) -> None:
        if not bool(getattr(self.controller, "is_running", False)):
            self._timer.stop()
            self._render()
            return
        self.controller.tick(self.settings.refresh_interval_ms)
        self._render()

    def _render(self) -> None:
        state = MainWindowState.from_controller(self.controller)
        is_live_mode = state.diagnostics.runtime_mode_label == "Live"
        self.setWindowTitle(state.title)
        self._title_label.setText(state.title)
        self._session_chip.setText(state.session_name)
        self._session_chip.setStyleSheet(self._chip_style("#202634"))
        self._mode_chip.setText(state.diagnostics.runtime_mode_label)
        self._mode_chip.setStyleSheet(self._chip_style("#0f3d4c"))
        self._focus_chip.setText(state.diagnostics.game_focus_label)
        self._focus_chip.setToolTip(state.diagnostics.window_binding_label)
        self._focus_chip.setStyleSheet(
            self._chip_style("#14532d" if state.diagnostics.game_focus_label == "Focused" else "#3b2f1a")
        )
        self._timer_chip.setText(state.diagnostics.session_time_label)
        self._timer_chip.setStyleSheet(self._chip_style("#2b243b"))
        self._model_chip.setText(self._model_summary_text(state))
        self._model_chip.setToolTip(state.metrics.ml_model_info.display_text)
        self._model_chip.setStyleSheet(
            self._chip_style(
                "#17324a" if state.metrics.ml_model_info.sample_count > 0 else "#4a2d12"
            )
        )
        self._status_chip.setText("RUNNING" if state.is_running else "READY")
        self._status_chip.setStyleSheet(
            self._status_chip_style(state.metrics.status_label, state.is_running)
        )
        self._status_label.setText(state.metrics.status_label)
        self._status_label.setToolTip(state.diagnostics.window_binding_label)
        self._total_value.setText(state.metrics.total_damage_label)
        self._dps_value.setText(state.metrics.rolling_dps_label)
        self._biggest_value.setText(state.metrics.biggest_hit_label)
        self._last_value.setText(state.metrics.last_hit_label)
        self._start_button.setText(state.start_button_label)
        self._start_button.setDisabled(state.is_running)
        self._stop_button.setDisabled(not state.is_running)
        self._overlay_card.setVisible(is_live_mode)
        self._sync_overlay_controls()

        self._hits_list.clear()
        if state.metrics.recent_hits:
            for hit in state.metrics.recent_hits:
                self._hits_list.addItem(hit)
        else:
            placeholder = QListWidgetItem("Waiting for hits")
            placeholder.setForeground(QColor("#7f8a9a"))
            self._hits_list.addItem(placeholder)

        for listener in self._render_listeners:
            listener(state)

    def add_render_listener(self, listener: Callable[[MainWindowState], None]) -> None:
        self._render_listeners.append(listener)

    def add_overlay_config_listener(
        self, listener: Callable[[OverlayConfig], None]
    ) -> None:
        self._overlay_config_listeners.append(listener)

    def add_overlay_enabled_listener(self, listener: Callable[[bool], None]) -> None:
        self._overlay_enabled_listeners.append(listener)

    def add_close_listener(self, listener: Callable[[], None]) -> None:
        self._close_listeners.append(listener)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._timer.stop()
        for listener in self._close_listeners:
            listener()
        if hasattr(self.controller, "stop"):
            self.controller.stop()
        super().closeEvent(event)


def run_main_shell(
    controller: object,
    configure_window: Callable[[MainShellWindow], None] | None = None,
) -> int:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv)
    window = MainShellWindow(controller)
    if configure_window is not None:
        configure_window(window)
    window.show()
    if owns_app:
        return app.exec()
    return 0
