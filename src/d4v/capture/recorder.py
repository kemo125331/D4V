from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import threading
import time

import mss
import mss.tools

from d4v.capture.game_window import get_diablo_iv_bounds


@dataclass(frozen=True)
class CaptureSessionConfig:
    session_name: str
    fps: int = 10


class FrameRecorder:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._session_dir: Path | None = None
        self._frames_written = 0
        self._started_at: float | None = None
        self._config: CaptureSessionConfig | None = None

    @property
    def session_dir(self) -> Path | None:
        return self._session_dir

    @property
    def is_recording(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def frames_written(self) -> int:
        return self._frames_written

    def start(self, config: CaptureSessionConfig) -> Path:
        if self.is_recording:
            raise RuntimeError("Recorder is already running.")

        session_dir = self.base_dir / config.session_name
        session_dir.mkdir(parents=True, exist_ok=True)

        self._config = config
        self._session_dir = session_dir
        self._frames_written = 0
        self._started_at = time.time()
        self._stop_event.clear()
        self._write_metadata(status="recording")

        self._thread = threading.Thread(
            target=self._record_loop,
            name="d4v-frame-recorder",
            daemon=True,
        )
        self._thread.start()
        return session_dir

    def stop(self) -> Path | None:
        if not self.is_recording:
            return self._session_dir

        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._thread = None
        self._write_metadata(status="stopped")
        return self._session_dir

    def _record_loop(self) -> None:
        assert self._session_dir is not None
        assert self._config is not None
        frame_delay = 1 / max(self._config.fps, 1)

        with mss.mss() as sct:
            while not self._stop_event.is_set():
                started = time.perf_counter()
                
                bounds = get_diablo_iv_bounds()
                if bounds is not None:
                    monitor = {
                        "left": bounds.left,
                        "top": bounds.top,
                        "width": bounds.width,
                        "height": bounds.height,
                    }
                    shot = sct.grab(monitor)
                    frame_path = self._session_dir / f"frame_{self._frames_written:06d}.png"
                    mss.tools.to_png(shot.rgb, shot.size, output=str(frame_path))
                    self._frames_written += 1

                elapsed = time.perf_counter() - started
                remaining = frame_delay - elapsed
                if remaining > 0:
                    time.sleep(remaining)

    def _write_metadata(self, status: str) -> None:
        if self._session_dir is None or self._config is None:
            return

        metadata = {
            "session_name": self._config.session_name,
            "fps": self._config.fps,
            "status": status,
            "frames_written": self._frames_written,
            "started_at_epoch_s": self._started_at,
        }
        (self._session_dir / "metadata.json").write_text(
            json.dumps(metadata, indent=2),
            encoding="utf-8",
        )
