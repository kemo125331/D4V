from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from d4v.overlay.view_model import PreviewViewModel


class PreviewWindow:
    def __init__(self, controller: object) -> None:
        self.controller = controller
        self.root = tk.Tk()
        self.root.title(str(getattr(self.controller, "window_title", "D4V Preview")))
        self.root.geometry("420x420")
        self._job: str | None = None

        self._total_var = tk.StringVar()
        self._dps_var = tk.StringVar()
        self._biggest_var = tk.StringVar()
        self._last_hit_var = tk.StringVar()
        self._status_var = tk.StringVar()

        self._build_ui()
        self._render()

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            outer,
            text=str(getattr(self.controller, "window_title", "D4V Preview")),
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            outer,
            text=f"Session: {self.controller.session_name}",
        ).pack(anchor="w", pady=(4, 12))

        self._metric_row(outer, "Total Damage", self._total_var)
        self._metric_row(outer, "Rolling DPS", self._dps_var)
        self._metric_row(outer, "Biggest Hit", self._biggest_var)
        self._metric_row(outer, "Last Hit", self._last_hit_var)
        self._metric_row(outer, "Status", self._status_var)

        controls = ttk.Frame(outer)
        controls.pack(anchor="w", pady=(16, 0))
        ttk.Button(
            controls,
            text=str(getattr(self.controller, "start_button_label", "Start")),
            command=self.start,
        ).pack(side=tk.LEFT)
        ttk.Button(controls, text="Stop", command=self.stop).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(controls, text="Reset", command=self.reset).pack(side=tk.LEFT, padx=(8, 0))

        log_frame = ttk.LabelFrame(outer, text="Recent Hits Log")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(16, 0))

        self._listbox = tk.Listbox(log_frame, height=6, font=("Consolas", 10))
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self._listbox.yview)
        self._listbox.configure(yscrollcommand=scrollbar.set)

        self._listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 0), pady=4)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=4)

    def _metric_row(self, parent: ttk.Frame, label: str, variable: tk.StringVar) -> None:
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=2)
        ttk.Label(row, text=f"{label}:", width=14).pack(side=tk.LEFT)
        ttk.Label(row, textvariable=variable).pack(side=tk.LEFT)

    def start(self) -> None:
        self.controller.start()
        self._schedule_tick()
        self._render()

    def stop(self) -> None:
        self.controller.stop()
        if self._job is not None:
            self.root.after_cancel(self._job)
            self._job = None
        self._render()

    def reset(self) -> None:
        self.controller.reset()
        self._render()

    def _schedule_tick(self) -> None:
        if not self.controller.is_running:
            self._job = None
            return
        self.controller.tick(100)
        self._render()
        self._job = self.root.after(100, self._schedule_tick)

    def _render(self) -> None:
        view_model = self.controller.view_model()
        self._apply_view_model(view_model)

    def _apply_view_model(self, view_model: PreviewViewModel) -> None:
        self._total_var.set(view_model.total_damage_label)
        self._dps_var.set(view_model.rolling_dps_label)
        self._biggest_var.set(view_model.biggest_hit_label)
        self._last_hit_var.set(view_model.last_hit_label)
        self._status_var.set(view_model.status_label)

        self._listbox.delete(0, tk.END)
        for hit_str in view_model.recent_hits:
            self._listbox.insert(tk.END, hit_str)
        if view_model.recent_hits:
            self._listbox.yview_moveto(1.0)

    def run(self) -> int:
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()
        return 0

    def _on_close(self) -> None:
        self.stop()
        self.root.destroy()
