"""Transparent in-game overlay for Diablo IV.

Displays combat stats (AVG DMG, LAST DMG, etc.) in the bottom-left corner
of the game window with a transparent background.
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass, field
from pathlib import Path

from d4v.capture.game_window import get_diablo_iv_bounds
from d4v.domain.session_stats import SessionStats


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
    - Has a transparent background
    - Stays on top of other windows
    - Positions at bottom-left of the game window
    - Shows damage stats with minimal visual footprint
    """
    
    def __init__(self, controller: GameOverlayController, auto_start: bool = True, debug: bool = False, use_toplevel: bool = False) -> None:
        self.controller = controller
        self.use_toplevel = use_toplevel
        self._user_moved = False  # Track if user has manually moved the window
        
        if use_toplevel:
            # Use Toplevel when embedded with another Tk window
            self.root = tk.Toplevel()
        else:
            # Use Tk() for standalone mode
            self.root = tk.Tk()
        
        # Debug mode: visible window with border
        if debug:
            self.root.overrideredirect(False)
            self.root.attributes("-topmost", True)
            self.root.configure(bg="red")
        else:
            # Remove window decorations but allow dragging
            self.root.overrideredirect(True)
            # Make background transparent - use a specific color that's not used elsewhere
            self.root.attributes("-transparentcolor", "#000001")
            self.root.attributes("-topmost", True)
            # Set root background to transparency color
            self.root.configure(bg="#000001")
        
        # Set initial window size (will be updated by content)
        self.root.geometry("250x220")

        # Set window style for click-through (optional)
        # Note: This requires additional Windows API calls

        self._avg_var = tk.StringVar(value="--")
        self._last_var = tk.StringVar(value="--")
        self._total_var = tk.StringVar(value="0")
        self._hits_var = tk.StringVar(value="0")
        self._dps_var = tk.StringVar(value="0")

        self._job: str | None = None
        self._build_ui()
        self._update_position()
        
        # Enable window dragging
        self._enable_drag()

        # Auto-start the overlay
        if auto_start:
            self.controller.start()
            self._schedule_tick()
        
    def _build_ui(self) -> None:
        """Build the overlay UI."""
        # Main frame with semi-transparent background
        main_frame = tk.Frame(
            self.root,
            bg="#1a1a1a",
            padx=12,
            pady=8,
        )
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = tk.Label(
            main_frame,
            text="D4V Combat",
            bg="#1a1a1a",
            fg="#888888",
            font=("Segoe UI", 9, "bold"),
            anchor="w",
        )
        title_label.pack(anchor="w", pady=(0, 6))
        
        # Separator line
        separator = tk.Frame(main_frame, bg="#333333", height=1)
        separator.pack(fill=tk.X, pady=(0, 6))
        
        # Stats grid
        stats_frame = tk.Frame(main_frame, bg="#1a1a1a")
        stats_frame.pack(fill=tk.BOTH, expand=True)
        
        # AVG DMG (primary stat - larger)
        self._create_stat_row(
            stats_frame,
            "AVG DMG",
            self._avg_var,
            row=0,
            value_font=("Segoe UI", 18, "bold"),
            value_fg="#00ff00",
        )
        
        # LAST DMG (secondary stat - larger)
        self._create_stat_row(
            stats_frame,
            "LAST DMG",
            self._last_var,
            row=1,
            value_font=("Segoe UI", 18, "bold"),
            value_fg="#ffff00",
        )
        
        # Separator
        separator2 = tk.Frame(main_frame, bg="#333333", height=1)
        separator2.pack(fill=tk.X, pady=(6, 6))
        
        # Secondary stats (smaller)
        self._create_stat_row(
            stats_frame,
            "DPS",
            self._dps_var,
            row=2,
            value_font=("Segoe UI", 11),
            value_fg="#ffffff",
        )
        
        self._create_stat_row(
            stats_frame,
            "TOTAL",
            self._total_var,
            row=3,
            value_font=("Segoe UI", 11),
            value_fg="#ffffff",
        )
        
        self._create_stat_row(
            stats_frame,
            "HITS",
            self._hits_var,
            row=4,
            value_font=("Segoe UI", 11),
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
        row_frame = tk.Frame(parent, bg="#1a1a1a")
        row_frame.pack(anchor="w", pady=1)
        
        label_label = tk.Label(
            row_frame,
            text=label,
            bg="#1a1a1a",
            fg="#666666",
            font=("Segoe UI", 9),
            width=10,
            anchor="w",
        )
        label_label.pack(side=tk.LEFT)
        
        value_label = tk.Label(
            row_frame,
            textvariable=variable,
            bg="#1a1a1a",
            fg=value_fg,
            font=value_font,
            anchor="e",
        )
        value_label.pack(side=tk.LEFT)

    def _enable_drag(self) -> None:
        """Enable window dragging functionality."""
        self._drag_data = {"x": 0, "y": 0, "active": False}
        
        # Bind mouse events to the main frame and all child widgets
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
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y
        self._drag_data["active"] = True
    
    def _on_drag_end(self, event: tk.Event) -> None:
        """Handle drag end."""
        self._drag_data["active"] = False
        self._user_moved = True  # Mark that user has manually moved the window
    
    def _on_drag_motion(self, event: tk.Event) -> None:
        """Handle drag motion."""
        if not self._drag_data["active"]:
            return
        
        # Calculate new position
        delta_x = event.x - self._drag_data["x"]
        delta_y = event.y - self._drag_data["y"]
        
        # Get current window position
        x = self.root.winfo_x() + delta_x
        y = self.root.winfo_y() + delta_y
        
        # Move window
        self.root.geometry(f"+{x}+{y}")

    def _update_position(self) -> None:
        """Update window position to bottom-left of game window."""
        # Don't auto-update position if user has manually dragged the window
        if self._user_moved:
            return
            
        bounds = get_diablo_iv_bounds()

        if bounds is None:
            # Fallback to screen bottom-left
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            x = 20
            y = screen_height - 200
        else:
            # Position at bottom-left of game window
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
        
        # Force UI update
        self.root.update_idletasks()
    
    def run(self) -> int:
        """Run the overlay main loop."""
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()
        return 0
    
    def _on_close(self) -> None:
        """Handle window close."""
        self.stop()
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
