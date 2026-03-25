from pathlib import Path
import tkinter as tk
from tkinter import ttk

from d4v.capture.recorder import CaptureSessionConfig, FrameRecorder

ROUND_GUIDANCE = """Record 3 short clips:

1. Single-target test
2. Dense-pack test
3. Damage + gold/item noise test

Recommended:
- Borderless windowed mode
- Same resolution and HUD settings for all clips
- Prefer 60 FPS
- Prefer SDR for the first pass
- Do not crop the video

Save samples under:
fixtures/replays/<session-name>/
"""


class CaptureRoundApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("D4V Capture Round Assistant")
        self.root.geometry("640x420")
        self._seconds = 0
        self._timer_running = False
        self._timer_job: str | None = None
        self._replay_dir = Path.cwd() / "fixtures" / "replays"
        self._replay_dir.mkdir(parents=True, exist_ok=True)
        self._recorder = FrameRecorder(self._replay_dir)
        self._session_name_var = tk.StringVar(value="first-round")
        self._fps_var = tk.StringVar(value="10")

        self._build_ui()

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill=tk.BOTH, expand=True)

        title = ttk.Label(
            outer,
            text="D4V Capture Round Assistant",
            font=("Segoe UI", 16, "bold"),
        )
        title.pack(anchor="w")

        subtitle = ttk.Label(
            outer,
            text="Use this while you record the first combat samples for damage analysis.",
        )
        subtitle.pack(anchor="w", pady=(4, 12))

        self.status_var = tk.StringVar(value="Status: ready")
        status = ttk.Label(outer, textvariable=self.status_var)
        status.pack(anchor="w", pady=(0, 8))

        session_row = ttk.Frame(outer)
        session_row.pack(anchor="w", fill=tk.X, pady=(0, 8))

        ttk.Label(session_row, text="Session name:").pack(side=tk.LEFT)
        ttk.Entry(session_row, textvariable=self._session_name_var, width=24).pack(side=tk.LEFT, padx=(8, 16))
        ttk.Label(session_row, text="FPS:").pack(side=tk.LEFT)
        ttk.Entry(session_row, textvariable=self._fps_var, width=6).pack(side=tk.LEFT, padx=(8, 0))

        self.timer_var = tk.StringVar(value="00:00")
        timer = ttk.Label(
            outer,
            textvariable=self.timer_var,
            font=("Consolas", 24, "bold"),
        )
        timer.pack(anchor="w", pady=(0, 12))

        controls = ttk.Frame(outer)
        controls.pack(anchor="w", pady=(0, 12))

        ttk.Button(controls, text="Start Round", command=self.start_round).pack(side=tk.LEFT)
        ttk.Button(controls, text="Stop Round", command=self.stop_round).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(controls, text="Reset Timer", command=self.reset_timer).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(controls, text="Open Replay Folder", command=self.open_replay_folder).pack(side=tk.LEFT, padx=(8, 0))

        text = tk.Text(outer, wrap="word", height=16)
        text.insert("1.0", ROUND_GUIDANCE)
        text.config(state=tk.DISABLED)
        text.pack(fill=tk.BOTH, expand=True)

    def start_round(self) -> None:
        if self._recorder.is_recording:
            return
        try:
            fps = int(self._fps_var.get())
        except ValueError:
            self.status_var.set("Status: invalid FPS value")
            return
        session_name = self._session_name_var.get().strip() or "capture-round"
        session_dir = self._recorder.start(CaptureSessionConfig(session_name=session_name, fps=fps))
        self.status_var.set(f"Status: recording to {session_dir.name}")
        self.start_timer()
        self.root.after(150, self.root.iconify)

    def stop_round(self) -> None:
        session_dir = self._recorder.stop()
        self.stop_timer()
        if session_dir is None:
            self.status_var.set("Status: round stopped")
            return
        self.status_var.set(
            f"Status: saved {self._recorder.frames_written} frames to {session_dir.name}"
        )

    def start_timer(self) -> None:
        if self._timer_running:
            return
        self._timer_running = True
        self._tick()

    def stop_timer(self) -> None:
        self._timer_running = False
        if self._timer_job is not None:
            self.root.after_cancel(self._timer_job)
            self._timer_job = None

    def reset_timer(self) -> None:
        self.stop_timer()
        self._seconds = 0
        self._update_timer_label()
        self.status_var.set("Status: ready")

    def open_replay_folder(self) -> None:
        replay_dir = Path.cwd() / "fixtures" / "replays"
        replay_dir.mkdir(parents=True, exist_ok=True)
        self.status_var.set(f"Status: opened {replay_dir}")
        import os

        os.startfile(replay_dir)  # type: ignore[attr-defined]

    def _tick(self) -> None:
        if not self._timer_running:
            return
        self._seconds += 1
        self._update_timer_label()
        self._timer_job = self.root.after(1000, self._tick)

    def _update_timer_label(self) -> None:
        minutes, seconds = divmod(self._seconds, 60)
        self.timer_var.set(f"{minutes:02d}:{seconds:02d}")

    def run(self) -> int:
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()
        return 0

    def _on_close(self) -> None:
        self._recorder.stop()
        self.root.destroy()


def main() -> int:
    app = CaptureRoundApp()
    return app.run()
