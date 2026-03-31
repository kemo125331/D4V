"""Transparent in-game overlay for Diablo IV.

Displays combat stats (AVG DMG, LAST DMG, etc.) in the bottom-left corner
of the game window with a transparent background.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import tkinter as tk
from dataclasses import dataclass, field
from pathlib import Path

from d4v.capture.game_window import get_diablo_iv_bounds
from d4v.domain.session_stats import SessionStats
from d4v.overlay.config import OverlayConfig, load_overlay_config, save_overlay_config


# Windows constants for click-through
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
LWA_ALPHA = 0x00000002


def format_damage_value(value: int | float) -> str:
    """Format damage value for display with K/M/B/T suffixes."""
    if value is None or value == 0:
        return "0"

    value = float(value)

    # Trillions
    if value >= 1_000_000_000_000:
        suffix = "T"
        value /= 1_000_000_000_000
    # Billions
    elif value >= 1_000_000_000:
        suffix = "B"
        value /= 1_000_000_000
    # Millions
    elif value >= 1_000_000:
        suffix = "M"
        value /= 1_000_000
    # Thousands
    elif value >= 1_000:
        suffix = "K"
        value /= 1_000
    else:
        # Small numbers - show as integer
        return str(int(value))

    # Format with 1 decimal place, remove trailing zeros
    formatted = f"{value:.1f}{suffix}"
    # Remove .0 if present (e.g., "10.0K" -> "10K")
    if formatted.endswith(".0"):
        formatted = formatted[:-2] + suffix

    return formatted


@dataclass
class GameOverlayViewModel:
    """View model for game overlay."""

    avg_damage_label: str = "0"
    last_damage_label: str = "--"
    total_damage_label: str = "0"
    hits_count_label: str = "0"
    dps_label: str = "0"

    @classmethod
    def from_stats(
        cls,
        *,
        avg_damage: float,
        last_damage: int | None,
        total_damage: int,
        hits_count: int,
        dps: float,
    ) -> "GameOverlayViewModel":
        """Create view model from stats."""
        return cls(
            avg_damage_label=format_damage_value(avg_damage),
            last_damage_label=format_damage_value(last_damage) if last_damage else "--",
            total_damage_label=format_damage_value(total_damage),
            hits_count_label=str(hits_count),
            dps_label=format_damage_value(dps),
        )


class GameOverlayWindow:
    """Transparent overlay window for in-game stats display.

    This window:
    - Has a true transparent background using -alpha
    - Stays on top of other windows
    - Positions at bottom-left of the game window
    - Shows damage stats with minimal visual footprint
    - Supports click-through to the game window
    """

    def __init__(
        self,
        controller: GameOverlayController,
        auto_start: bool = True,
        debug: bool = False,
        use_toplevel: bool = False,
        config: OverlayConfig | None = None,
    ) -> None:
        self.controller = controller
        self.use_toplevel = use_toplevel
        self._user_moved = False
        self._click_through_enabled = False

        # Load config
        self.config = config if config is not None else load_overlay_config()

        if use_toplevel:
            self.root = tk.Toplevel()
        else:
            self.root = tk.Tk()

        # Debug mode: visible window with border
        if debug:
            self.root.overrideredirect(False)
            self.root.attributes("-topmost", True)
            self.root.configure(bg="red")
        else:
            self.root.overrideredirect(True)
            self.root.attributes("-topmost", True)
            self.root.attributes("-alpha", self.config.opacity)
            self.root.configure(bg=self.config.bg_color)

        self.root.geometry("250x220")

        self._avg_var = tk.StringVar(value="--")
        self._last_var = tk.StringVar(value="--")
        self._total_var = tk.StringVar(value="0")
        self._hits_var = tk.StringVar(value="0")
        self._dps_var = tk.StringVar(value="0")

        self._job: str | None = None
        self._build_ui()
        self._update_position()
        self._enable_drag()

        # Apply click-through after window is created
        if self.config.click_through and not debug:
            self.root.after(100, self._enable_click_through)

        if auto_start:
            self.controller.start()
            self._schedule_tick()

    def _build_ui(self) -> None:
        """Build the overlay UI."""
        main_frame = tk.Frame(
            self.root,
            bg=self.config.bg_color,
            padx=10,
            pady=6,
        )
        main_frame.pack(fill=tk.BOTH, expand=True)

        title_label = tk.Label(
            main_frame,
            text="D4V Combat",
            bg=self.config.bg_color,
            fg=self.config.title_color,
            font=(self.config.font_family, 9, "bold"),
            anchor="w",
        )
        title_label.pack(anchor="w", pady=(0, 4))

        separator = tk.Frame(main_frame, bg=self.config.separator_color, height=1)
        separator.pack(fill=tk.X, pady=(0, 4))

        stats_frame = tk.Frame(main_frame, bg=self.config.bg_color)
        stats_frame.pack(fill=tk.BOTH, expand=True)

        value_size = max(self.config.font_size, 14)

        self._create_stat_row(
            stats_frame,
            "AVG DMG",
            self._avg_var,
            row=0,
            value_font=(self.config.font_family, value_size + 4, "bold"),
            value_fg=self.config.text_color,
        )

        self._create_stat_row(
            stats_frame,
            "LAST DMG",
            self._last_var,
            row=1,
            value_font=(self.config.font_family, value_size + 4, "bold"),
            value_fg="#ffff00",
        )

        separator2 = tk.Frame(main_frame, bg=self.config.separator_color, height=1)
        separator2.pack(fill=tk.X, pady=(4, 4))

        secondary_size = max(self.config.font_size, 11)

        self._create_stat_row(
            stats_frame,
            "DPS",
            self._dps_var,
            row=2,
            value_font=(self.config.font_family, secondary_size),
            value_fg="#ffffff",
        )

        self._create_stat_row(
            stats_frame,
            "TOTAL",
            self._total_var,
            row=3,
            value_font=(self.config.font_family, secondary_size),
            value_fg="#ffffff",
        )

        self._create_stat_row(
            stats_frame,
            "HITS",
            self._hits_var,
            row=4,
            value_font=(self.config.font_family, secondary_size),
            value_fg="#ffffff",
        )

    def _create_stat_row(
        self,
        parent: tk.Frame,
        label: str,
        variable: tk.StringVar,
        row: int,
        value_font: tuple[str, int, str] | tuple[str, int] = ("Segoe UI", 12),
        value_fg: str = "#ffffff",
    ) -> None:
        """Create a stat row with label and value."""
        row_frame = tk.Frame(parent, bg=self.config.bg_color)
        row_frame.pack(anchor="w", pady=1)

        label_label = tk.Label(
            row_frame,
            text=label,
            bg=self.config.bg_color,
            fg=self.config.label_color,
            font=(self.config.font_family, 9),
            width=10,
            anchor="w",
        )
        label_label.pack(side=tk.LEFT)

        value_label = tk.Label(
            row_frame,
            textvariable=variable,
            bg=self.config.bg_color,
            fg=value_fg,
            font=value_font,
            anchor="e",
        )
        value_label.pack(side=tk.LEFT)

    def _enable_click_through(self) -> None:
        """Enable click-through using Windows API."""
        try:
            hwnd = self.root.winfo_id()
            ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ex_style |= WS_EX_LAYERED | WS_EX_TRANSPARENT
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)
            self._click_through_enabled = True
        except (AttributeError, OSError):
            pass

    def _disable_click_through(self) -> None:
        """Disable click-through so window can receive clicks."""
        try:
            hwnd = self.root.winfo_id()
            ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ex_style &= ~WS_EX_TRANSPARENT
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)
            self._click_through_enabled = False
        except (AttributeError, OSError):
            pass

    def toggle_click_through(self) -> None:
        """Toggle click-through mode."""
        if self._click_through_enabled:
            self._disable_click_through()
        else:
            self._enable_click_through()

    def set_click_through(self, enabled: bool) -> None:
        """Set click-through state."""
        if enabled and not self._click_through_enabled:
            self._enable_click_through()
        elif not enabled and self._click_through_enabled:
            self._disable_click_through()

    def _enable_drag(self) -> None:
        """Enable window dragging functionality."""
        self._drag_data = {"x": 0, "y": 0, "active": False}

        widgets = [self.root]
        for widget in self.root.winfo_children():
            widgets.append(widget)
            for child in widget.winfo_children():
                widgets.append(child)

        for widget in widgets:
            widget.bind("<ButtonPress-1>", self._on_drag_start)
            widget.bind("<ButtonRelease-1>", self._on_drag_end)
            widget.bind("<B1-Motion>", self._on_drag_motion)

    def _on_drag_start(self, event: tk.Event) -> None:
        """Handle drag start."""
        # Temporarily disable click-through during drag
        if self._click_through_enabled:
            self._disable_click_through()
            self._drag_data["was_click_through"] = True
        else:
            self._drag_data["was_click_through"] = False

        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y
        self._drag_data["active"] = True

    def _on_drag_end(self, event: tk.Event) -> None:
        """Handle drag end."""
        self._drag_data["active"] = False
        self._user_moved = True

        # Save position
        self._save_position()

        # Restore click-through if it was enabled
        if self._drag_data.get("was_click_through") and self.config.click_through:
            self.root.after(500, self._enable_click_through)

    def _on_drag_motion(self, event: tk.Event) -> None:
        """Handle drag motion."""
        if not self._drag_data["active"]:
            return

        delta_x = event.x - self._drag_data["x"]
        delta_y = event.y - self._drag_data["y"]

        x = self.root.winfo_x() + delta_x
        y = self.root.winfo_y() + delta_y

        self.root.geometry(f"+{x}+{y}")

    def _save_position(self) -> None:
        """Save current window position to config."""
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        self.config.position = (x, y)
        save_overlay_config(self.config)

    def _update_position(self) -> None:
        """Update window position to bottom-left of game window."""
        # Use saved position if user has moved the window
        if self._user_moved:
            return

        # Use config position if set
        if self.config.position is not None:
            x, y = self.config.position
            self.root.geometry(f"+{x}+{y}")
            return

        bounds = get_diablo_iv_bounds()

        if bounds is None:
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            x = 20
            y = screen_height - 200
        else:
            x = bounds.left + 20
            y = bounds.top + bounds.height - 200

        self.root.geometry(f"+{x}+{y}")

    def start(self) -> None:
        """Start the overlay."""
        self._schedule_tick()

    def stop(self) -> None:
        """Stop the overlay."""
        if self._job is not None:
            self.root.after_cancel(self._job)
            self._job = None

    def reset(self) -> None:
        """Reset the overlay."""
        self.controller.reset()
        self._render()

    def _schedule_tick(self) -> None:
        """Schedule next update tick."""
        if not self.controller.is_running:
            self._job = None
            return

        self.controller.tick(100)
        self._render()
        self._update_position()
        self._job = self.root.after(100, self._schedule_tick)

    def _render(self) -> None:
        """Render current state."""
        view_model = self.controller.view_model()
        self._apply_view_model(view_model)

    def _apply_view_model(self, view_model: GameOverlayViewModel) -> None:
        """Apply view model to UI."""
        self._avg_var.set(view_model.avg_damage_label)
        self._last_var.set(view_model.last_damage_label)
        self._total_var.set(view_model.total_damage_label)
        self._hits_var.set(view_model.hits_count_label)
        self._dps_var.set(view_model.dps_label)

        self.root.update_idletasks()

    def run(self) -> int:
        """Run the overlay main loop."""
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()
        return 0

    def _on_close(self) -> None:
        """Handle window close."""
        self.stop()
        self._save_position()
        self.root.destroy()


@dataclass
class GameOverlayController:
    """Controller for game overlay."""

    stats: SessionStats | None = None
    last_hit: int | None = None
    status: str = "Ready"
    elapsed_ms: int = 0
    is_running: bool = False

    def __post_init__(self) -> None:
        """Initialize stats if not provided."""
        if self.stats is None:
            self.stats = SessionStats()

    def start(self) -> None:
        """Start the controller."""
        self.is_running = True
        self.status = "Running"

    def stop(self) -> None:
        """Stop the controller."""
        self.is_running = False
        self.status = "Stopped"

    def reset(self) -> None:
        """Reset the controller."""
        if self.stats:
            self.stats.reset()
        self.last_hit = None
        self.status = "Ready"
        self.elapsed_ms = 0
        self.is_running = False

    def tick(self, delta_ms: int) -> None:
        """Update controller state."""
        if not self.is_running:
            return

        self.elapsed_ms += delta_ms
        self.status = f"Running ({self.elapsed_ms} ms)"

    def add_hit(self, value: int) -> None:
        """Add a hit to the stats."""
        self.last_hit = value
        if self.stats:
            self.stats.add_hit(
                frame=0,
                timestamp_ms=self.elapsed_ms,
                value=value,
                confidence=1.0,
            )

    def view_model(self) -> GameOverlayViewModel:
        """Get current view model."""
        if not self.stats:
            self.stats = SessionStats()

        return GameOverlayViewModel.from_stats(
            avg_damage=self.stats.average_hit,
            last_damage=self.last_hit,
            total_damage=self.stats.visible_damage_total,
            hits_count=self.stats.hit_count,
            dps=self.stats.rolling_dps(),
        )


def main() -> int:
    """Run the game overlay."""
    from d4v.domain.session_stats import SessionStats

    controller = GameOverlayController(stats=SessionStats())
    app = GameOverlayWindow(controller)
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
