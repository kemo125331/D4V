"""Configuration for the game overlay."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from d4v.ui.paths import app_data_dir


@dataclass
class OverlayConfig:
    """Configuration for the game overlay.

    Attributes:
        opacity: Window opacity (0.0 to 1.0).
        font_size: Base font size for stat values.
        text_color: Primary text color (green for AVG DMG).
        bg_color: Background frame color.
        click_through: Enable click-through to game window.
        position: Manual position override (x, y) or None for auto.
        font_family: Font family for text.
        title_color: Color for the title text.
        label_color: Color for stat labels.
        separator_color: Color for separator lines.
        mode: Overlay density preset.
    """

    opacity: float = 0.85
    font_size: int = 14
    text_color: str = "#00ff00"
    bg_color: str = "#1a1a1a"
    click_through: bool = True
    position: tuple[int, int] | None = None
    font_family: str = "Segoe UI"
    title_color: str = "#888888"
    label_color: str = "#666666"
    separator_color: str = "#333333"
    mode: str = "expanded"


def load_overlay_config(path: Path | None = None) -> OverlayConfig:
    """Load overlay configuration from JSON file.

    Args:
        path: Path to config file. Defaults to overlay_config.json in package dir.

    Returns:
        Loaded OverlayConfig with defaults for missing values.
    """
    if path is None:
        path = app_data_dir() / "overlay_config.json"

    if not path.exists():
        return OverlayConfig()

    try:
        data = json.loads(path.read_text())
        # Handle position tuple from JSON
        if "position" in data and data["position"] is not None:
            data["position"] = tuple(data["position"])
        return OverlayConfig(**data)
    except (json.JSONDecodeError, TypeError):
        return OverlayConfig()


def save_overlay_config(config: OverlayConfig, path: Path | None = None) -> None:
    """Save overlay configuration to JSON file.

    Args:
        config: OverlayConfig to save.
        path: Path to config file. Defaults to overlay_config.json in package dir.
    """
    if path is None:
        path = app_data_dir() / "overlay_config.json"

    data = asdict(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
