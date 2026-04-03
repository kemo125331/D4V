"""Shared overlay view model and controller logic."""

from __future__ import annotations

from dataclasses import dataclass

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
    formatted_value = f"{value:.1f}"
    if formatted_value.endswith(".0"):
        formatted_value = formatted_value[:-2]
    formatted = f"{formatted_value}{suffix}"

    return formatted


def format_elapsed_time(elapsed_ms: int) -> str:
    total_seconds = max(0, elapsed_ms // 1000)
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"


@dataclass
class GameOverlayViewModel:
    """View model for game overlay."""

    avg_damage_label: str = "0"
    last_damage_label: str = "--"
    total_damage_label: str = "0"
    hits_count_label: str = "0"
    dps_label: str = "0"
    peak_hit_label: str = "0"
    session_time_label: str = "00:00"

    @classmethod
    def from_stats(
        cls,
        *,
        avg_damage: float,
        last_damage: int | None,
        total_damage: int,
        hits_count: int,
        dps: float,
        peak_hit: int = 0,
        elapsed_ms: int = 0,
    ) -> "GameOverlayViewModel":
        """Create view model from stats."""
        return cls(
            avg_damage_label=format_damage_value(avg_damage),
            last_damage_label=format_damage_value(last_damage) if last_damage else "--",
            total_damage_label=format_damage_value(total_damage),
            hits_count_label=str(hits_count),
            dps_label=format_damage_value(dps),
            peak_hit_label=format_damage_value(peak_hit),
            session_time_label=format_elapsed_time(elapsed_ms),
        )


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
            peak_hit=self.stats.biggest_hit,
            elapsed_ms=self.elapsed_ms,
        )


def main() -> int:
    """Run the Qt overlay runtime."""
    from d4v.ui.overlay_runtime import run_overlay_runtime

    return run_overlay_runtime(GameOverlayController())


if __name__ == "__main__":
    raise SystemExit(main())
