"""Resolution and UI scale auto-detection.

Automatically detects game resolution and UI scale settings,
and manages calibration profiles for different configurations.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol


class ResolutionDetector(Protocol):
    """Protocol for platform-specific resolution detection."""

    def detect_game_window(self) -> tuple[int, int, int, int] | None:
        """Detect game window bounds.

        Returns:
            Tuple of (left, top, right, bottom) or None.
        """
        ...


@dataclass(frozen=True)
class ResolutionProfile:
    """Calibration profile for a specific resolution.

    Attributes:
        resolution: Resolution string (e.g., "1920x1080").
        ui_scale: UI scale percentage.
        damage_roi: Calibrated damage ROI.
        ocr_settings: Calibrated OCR settings.
        color_thresholds: Calibrated color thresholds.
        created_date: Profile creation date.
        last_used: Last usage timestamp.
        usage_count: Number of times profile was used.
    """

    resolution: str
    ui_scale: float = 100.0
    damage_roi: tuple[float, float, float, float] = (0.15, 0.05, 0.70, 0.75)
    ocr_settings: dict[str, Any] = field(default_factory=dict)
    color_thresholds: dict[str, Any] = field(default_factory=dict)
    created_date: str = ""
    last_used: str = ""
    usage_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResolutionProfile:
        """Create from dictionary."""
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> ResolutionProfile:
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(json_str))


@dataclass
class ResolutionProfileManager:
    """Manages resolution profiles for different configurations.

    Example:
        manager = ResolutionProfileManager(
            profiles_dir=Path("profiles"),
        )

        # Load or create profile
        profile = manager.get_or_create_profile("1920x1080", 100.0)

        # Update profile
        manager.update_profile(profile.resolution, {
            "damage_roi": (0.10, 0.05, 0.75, 0.75),
        })

        # Save profile
        manager.save_profile(profile)
    """

    profiles_dir: Path = field(default_factory=lambda: Path("profiles"))
    profiles: dict[str, ResolutionProfile] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Initialize profile manager."""
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self._load_profiles()

    def _load_profiles(self) -> None:
        """Load existing profiles from disk."""
        for path in self.profiles_dir.glob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    profile = ResolutionProfile.from_dict(data)
                    self.profiles[profile.resolution] = profile
            except (json.JSONDecodeError, KeyError):
                pass

    def get_or_create_profile(
        self,
        resolution: str,
        ui_scale: float = 100.0,
    ) -> ResolutionProfile:
        """Get existing profile or create new one.

        Args:
            resolution: Resolution string.
            ui_scale: UI scale percentage.

        Returns:
            ResolutionProfile object.
        """
        if resolution in self.profiles:
            profile = self.profiles[resolution]
            profile.usage_count += 1
            return profile

        # Create new profile
        from datetime import datetime
        profile = ResolutionProfile(
            resolution=resolution,
            ui_scale=ui_scale,
            created_date=datetime.now().isoformat(),
        )
        self.profiles[resolution] = profile
        return profile

    def update_profile(
        self,
        resolution: str,
        updates: dict[str, Any],
    ) -> ResolutionProfile | None:
        """Update profile with new settings.

        Args:
            resolution: Resolution to update.
            updates: Dictionary of fields to update.

        Returns:
            Updated profile or None.
        """
        if resolution not in self.profiles:
            return None

        profile = self.profiles[resolution]

        # Update fields
        for key, value in updates.items():
            if hasattr(profile, key):
                object.__setattr__(profile, key, value)

        return profile

    def save_profile(self, profile: ResolutionProfile) -> None:
        """Save profile to disk.

        Args:
            profile: Profile to save.
        """
        from datetime import datetime
        profile.last_used = datetime.now().isoformat()

        path = self.profiles_dir / f"{profile.resolution.replace('x', '_')}.json"
        with open(path, "w", encoding="utf-8") as f:
            f.write(profile.to_json())

    def get_all_profiles(self) -> list[ResolutionProfile]:
        """Get all stored profiles.

        Returns:
            List of profiles.
        """
        return list(self.profiles.values())

    def delete_profile(self, resolution: str) -> bool:
        """Delete a profile.

        Args:
            resolution: Resolution to delete.

        Returns:
            True if deleted.
        """
        if resolution in self.profiles:
            del self.profiles[resolution]
            path = self.profiles_dir / f"{resolution.replace('x', '_')}.json"
            if path.exists():
                path.unlink()
            return True
        return False


def estimate_ui_scale(
    sample_frames: list[Any],
    expected_text_height: int = 24,
) -> float:
    """Estimate UI scale from sample frames.

    Args:
        sample_frames: List of sample frame images.
        expected_text_height: Expected text height at 100% scale.

    Returns:
        Estimated UI scale percentage.
    """
    if not sample_frames:
        return 100.0

    try:
        import cv2
        import numpy as np
    except ImportError:
        return 100.0

    # Analyze text sizes in samples
    measured_heights: list[float] = []

    for frame in sample_frames:
        # This would integrate with the vision pipeline
        # to measure actual text heights
        pass

    if not measured_heights:
        return 100.0

    avg_height = sum(measured_heights) / len(measured_heights)
    scale = (avg_height / expected_text_height) * 100

    # Round to nearest standard scale
    standard_scales = [100, 125, 150, 175, 200]
    return min(standard_scales, key=lambda x: abs(x - scale))


def detect_current_resolution() -> str:
    """Detect current screen resolution.

    Returns:
        Resolution string (e.g., "1920x1080").
    """
    try:
        from PIL import ImageGrab
        bbox = ImageGrab.grab().size
        return f"{bbox[0]}x{bbox[1]}"
    except Exception:
        return "1920x1080"  # Default
