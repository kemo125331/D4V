from __future__ import annotations

import subprocess
import tkinter as tk
from tkinter import ttk

from d4v.overlay.view_model import PreviewViewModel, MLModelInfo


class PreviewWindow:
    def __init__(self, controller: object) -> None:
        self.controller = controller
        self.root = tk.Tk()
        self.root.title(str(getattr(self.controller, "window_title", "D4V Preview")))
        self.root.geometry("500x500")
        self._job: str | None = None

        self._total_var = tk.StringVar()
        self._dps_var = tk.StringVar()
        self._biggest_var = tk.StringVar()
        self._last_hit_var = tk.StringVar()
        self._status_var = tk.StringVar()
        self._ml_model_var = tk.StringVar()

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

        # ML Model Status
        ml_frame = ttk.LabelFrame(outer, text="ML Detection Model", padding=8)
        ml_frame.pack(fill=tk.X, pady=(0, 12))

        self._ml_model_label = ttk.Label(
            ml_frame,
            textvariable=self._ml_model_var,
            font=("Segoe UI", 9),
        )
        self._ml_model_label.pack(anchor="w")

        # Train button row
        train_btn_frame = ttk.Frame(ml_frame)
        train_btn_frame.pack(anchor="w", pady=(8, 0))
        ttk.Button(
            train_btn_frame,
            text="🎯 Train Custom Model...",
            command=self._open_training_guide,
        ).pack(side=tk.LEFT)
        ttk.Label(
            train_btn_frame,
            text="  Collect gameplay data for a custom model",
            font=("Segoe UI", 8),
            foreground="gray",
        ).pack(side=tk.LEFT)

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
        ttk.Button(controls, text="Stop", command=self.stop).pack(
            side=tk.LEFT, padx=(8, 0)
        )
        ttk.Button(controls, text="Reset", command=self.reset).pack(
            side=tk.LEFT, padx=(8, 0)
        )

        log_frame = ttk.LabelFrame(outer, text="Recent Hits Log")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(16, 0))

        self._listbox = tk.Listbox(log_frame, height=6, font=("Consolas", 10))
        scrollbar = ttk.Scrollbar(
            log_frame, orient=tk.VERTICAL, command=self._listbox.yview
        )
        self._listbox.configure(yscrollcommand=scrollbar.set)

        self._listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 0), pady=4)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=4)

    def _metric_row(
        self, parent: ttk.Frame, label: str, variable: tk.StringVar
    ) -> None:
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
        self.controller.tick(50)
        self._render()
        self._job = self.root.after(50, self._schedule_tick)

    def _render(self) -> None:
        view_model = self.controller.view_model()
        self._apply_view_model(view_model)

    def _apply_view_model(self, view_model: PreviewViewModel) -> None:
        self._total_var.set(view_model.total_damage_label)
        self._dps_var.set(view_model.rolling_dps_label)
        self._biggest_var.set(view_model.biggest_hit_label)
        self._last_hit_var.set(view_model.last_hit_label)
        self._status_var.set(view_model.status_label)
        self._ml_model_var.set(view_model.ml_model_info.display_text)

        # Update ML model label color based on status
        self._ml_model_label.configure(foreground=view_model.ml_model_info.status_color)

        self._listbox.delete(0, tk.END)
        # Insert ML model status at top
        self._listbox.insert(tk.END, view_model.ml_model_info.display_text)
        self._listbox.itemconfig(0, foreground=view_model.ml_model_info.status_color)
        # Insert recent hits
        for hit_str in view_model.recent_hits:
            self._listbox.insert(tk.END, hit_str)
        if view_model.recent_hits:
            self._listbox.yview_moveto(1.0)

    def _open_training_guide(self) -> None:
        """Open the custom training guide in the default browser."""
        import webbrowser
        from pathlib import Path

        guide_path = (
            Path(__file__).parent.parent.parent.parent
            / "docs"
            / "CUSTOM_TRAINING_GUIDE.md"
        )
        if guide_path.exists():
            # Open the markdown file - it will open in default app or browser
            webbrowser.open(f"file://{guide_path.absolute()}")
        else:
            # Fallback: show a message box
            import tkinter.messagebox as messagebox

            messagebox.showinfo(
                "Training Guide",
                "Custom Training Guide not found.\n\n"
                "See docs/CUSTOM_TRAINING_GUIDE.md for instructions on training "
                "a custom model on your gameplay data.",
            )

    def run(self) -> int:
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()
        return 0

    def _on_close(self) -> None:
        self.stop()
        self.root.destroy()
