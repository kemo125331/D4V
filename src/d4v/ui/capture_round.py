from __future__ import annotations

import os
import sys
import time

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from d4v.capture.recorder import CaptureSessionConfig, FrameRecorder
from d4v.runtime_paths import replay_sessions_dir
from d4v.tools.capture_round import ROUND_GUIDANCE


def default_session_name() -> str:
    return f"session-{time.strftime('%Y%m%d-%H%M')}"


class CaptureRoundWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._seconds = 0
        self._timer_running = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._replay_dir = replay_sessions_dir()
        self._replay_dir.mkdir(parents=True, exist_ok=True)
        self._recorder = FrameRecorder(self._replay_dir)

        self._status_chip = QLabel("READY")
        self._status_label = QLabel("Ready to capture")
        self._session_name_input = QLineEdit(default_session_name())
        self._fps_select = QComboBox()
        self._timer_label = QLabel("00:00")
        self._save_path_label = QLabel(str(self._replay_dir))
        self._start_button = QPushButton("Start")
        self._stop_button = QPushButton("Stop")
        self._reset_button = QPushButton("Reset")
        self._open_button = QPushButton("Open Folder")

        self._build_ui()
        self._sync_actions()

    def _build_ui(self) -> None:
        self.setWindowTitle("D4V Capture")
        self.resize(720, 420)

        central = QWidget(self)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(14)

        title = QLabel("Capture")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        hero = self._card()
        hero_layout = hero.layout()
        assert isinstance(hero_layout, QVBoxLayout)
        hero_top = QHBoxLayout()
        hero_top.addWidget(title)
        hero_top.addStretch(1)
        hero_top.addWidget(self._status_chip)
        hero_layout.addLayout(hero_top)
        self._status_label.setStyleSheet("color: #a9b1ba;")
        hero_layout.addWidget(self._status_label)
        outer.addWidget(hero)

        session_card = self._card()
        session_layout = session_card.layout()
        assert isinstance(session_layout, QVBoxLayout)
        session_row = QHBoxLayout()
        session_row.addWidget(QLabel("Session"))
        self._session_name_input.setMaximumWidth(260)
        session_row.addWidget(self._session_name_input)
        session_row.addSpacing(12)
        session_row.addWidget(QLabel("FPS"))
        self._fps_select.addItems(["10", "15", "20", "30"])
        self._fps_select.setCurrentText("10")
        self._fps_select.setMaximumWidth(90)
        session_row.addWidget(self._fps_select)
        session_row.addStretch(1)
        session_layout.addLayout(session_row)

        path_row = QHBoxLayout()
        path_label = QLabel("Saves to")
        path_label.setStyleSheet("color: #7f8a9a;")
        self._save_path_label.setStyleSheet("color: #7f8a9a;")
        self._save_path_label.setWordWrap(True)
        path_row.addWidget(path_label)
        path_row.addWidget(self._save_path_label, stretch=1)
        session_layout.addLayout(path_row)
        outer.addWidget(session_card)

        self._timer_label.setFont(QFont("Consolas", 26, QFont.Weight.Bold))
        timer_card = self._card()
        timer_layout = timer_card.layout()
        assert isinstance(timer_layout, QVBoxLayout)
        timer_layout.addWidget(self._timer_label)
        outer.addWidget(timer_card)

        controls = QHBoxLayout()
        self._start_button.clicked.connect(self.start_round)
        self._stop_button.clicked.connect(self.stop_round)
        self._reset_button.clicked.connect(self.reset_timer)
        self._open_button.clicked.connect(self.open_replay_folder)
        controls.addWidget(self._start_button)
        controls.addWidget(self._stop_button)
        controls.addWidget(self._reset_button)
        controls.addWidget(self._open_button)
        controls.addStretch(1)
        outer.addLayout(controls)

        guide = self._card("Quick Pass")
        guide_layout = guide.layout()
        assert isinstance(guide_layout, QVBoxLayout)
        steps = QLabel(
            "1. Start capture\n"
            "2. Record a short single-target clip\n"
            "3. Record a dense-pack clip\n"
            "4. Record one clip with gold/item noise\n"
            "5. Stop and review the saved session"
        )
        steps.setStyleSheet("color: #cbd5e1;")
        steps.setWordWrap(True)
        guide_layout.addWidget(steps)
        outer.addWidget(guide, stretch=1)

        self.setStyleSheet(
            """
            QMainWindow {
                background: #0b0d12;
            }
            QLabel, QLineEdit, QComboBox {
                color: #f5f7fa;
            }
            QFrame#card {
                background: #141821;
                border: 1px solid #202634;
                border-radius: 12px;
            }
            QLineEdit, QComboBox {
                background: #10141c;
                border: 1px solid #202634;
                border-radius: 8px;
                padding: 8px;
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
            """
        )
        self.setCentralWidget(central)

    def _card(self, title: str | None = None) -> QFrame:
        frame = QFrame()
        frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)
        if title:
            label = QLabel(title)
            label.setStyleSheet("color: #8b949e; font-weight: 600;")
            layout.addWidget(label)
        return frame

    def _status_chip_style(self, recording: bool) -> str:
        if recording:
            return (
                "background: #7f1d1d; color: #fff5f5; border-radius: 999px; "
                "padding: 4px 10px; font-weight: 700;"
            )
        return (
            "background: #263041; color: #f5f7fa; border-radius: 999px; "
            "padding: 4px 10px; font-weight: 700;"
        )

    def _sync_actions(self) -> None:
        recording = self._recorder.is_recording
        self._start_button.setEnabled(not recording)
        self._stop_button.setEnabled(recording)
        self._session_name_input.setEnabled(not recording)
        self._fps_select.setEnabled(not recording)
        self._status_chip.setText("REC" if recording else "READY")
        self._status_chip.setStyleSheet(self._status_chip_style(recording))

    def start_round(self) -> None:
        if self._recorder.is_recording:
            return
        try:
            fps = int(self._fps_select.currentText())
        except ValueError:
            self._status_label.setText("Choose a valid FPS value")
            return
        session_name = self._session_name_input.text().strip() or default_session_name()
        session_dir = self._recorder.start(
            CaptureSessionConfig(session_name=session_name, fps=fps)
        )
        self._status_label.setText(f"Recording to {session_dir.name}")
        self.start_timer()
        self._sync_actions()
        QTimer.singleShot(150, self.showMinimized)

    def stop_round(self) -> None:
        session_dir = self._recorder.stop()
        self.stop_timer()
        if session_dir is None:
            self._status_label.setText("Capture stopped")
            self._sync_actions()
            return
        self._status_label.setText(
            f"Saved {self._recorder.frames_written} frames to {session_dir.name}"
        )
        self._sync_actions()

    def start_timer(self) -> None:
        if self._timer_running:
            return
        self._timer_running = True
        self._timer.start(1000)

    def stop_timer(self) -> None:
        self._timer_running = False
        self._timer.stop()

    def reset_timer(self) -> None:
        self.stop_timer()
        self._seconds = 0
        self._update_timer_label()
        if not self._recorder.is_recording:
            self._status_label.setText("Ready to capture")
            self._session_name_input.setText(default_session_name())
        self._sync_actions()

    def open_replay_folder(self) -> None:
        self._replay_dir.mkdir(parents=True, exist_ok=True)
        self._status_label.setText("Opened replay folder")
        os.startfile(self._replay_dir)  # type: ignore[attr-defined]

    def _tick(self) -> None:
        if not self._timer_running:
            return
        self._seconds += 1
        self._update_timer_label()

    def _update_timer_label(self) -> None:
        minutes, seconds = divmod(self._seconds, 60)
        self._timer_label.setText(f"{minutes:02d}:{seconds:02d}")

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._recorder.stop()
        self.stop_timer()
        self._sync_actions()
        super().closeEvent(event)


def run_capture_round() -> int:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv)
    window = CaptureRoundWindow()
    window.show()
    if owns_app:
        return app.exec()
    return 0
