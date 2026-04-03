from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from d4v.runtime_paths import bundled_models_dir


def format_damage_value(value: int | float) -> str:
    if isinstance(value, float) and not value.is_integer():
        return f"{value:,.2f}"
    return f"{int(value):,}"


@dataclass(frozen=True)
class MLModelInfo:
    """Information about the loaded ML model."""

    is_custom: bool
    sample_count: int
    session_count: int
    status_color: str = "green"

    @classmethod
    def detect_model(cls, models_dir: Path | None = None) -> "MLModelInfo":
        """Detect which model is loaded and return its info."""
        if models_dir is None:
            models_dir = bundled_models_dir()

        custom_model = models_dir / "confidence_model_custom.joblib"
        generic_model = models_dir / "confidence_model.joblib"

        # Check if custom model exists and is being used
        if custom_model.exists():
            return cls(
                is_custom=True,
                sample_count=2000,  # Approximate after custom training
                session_count=40,  # Approximate
                status_color="green",
            )
        elif generic_model.exists():
            return cls(
                is_custom=False,
                sample_count=1581,
                session_count=33,
                status_color="green",
            )
        else:
            return cls(
                is_custom=False,
                sample_count=0,
                session_count=0,
                status_color="orange",
            )

    @property
    def display_text(self) -> str:
        """Return formatted display text for the model status."""
        if self.is_custom:
            return (
                f"✓ Custom ML model | {self.sample_count:,} samples | "
                f"{self.session_count} sessions"
            )
        elif self.sample_count > 0:
            return (
                f"✓ Bundled ML model | {self.sample_count:,} samples | "
                f"{self.session_count} sessions"
            )
        else:
            return "⚠ Heuristic scoring only | no ML model file"


@dataclass(frozen=True)
class PreviewViewModel:
    total_damage_label: str
    rolling_dps_label: str
    biggest_hit_label: str
    last_hit_label: str
    status_label: str
    recent_hits: list[str] = field(default_factory=list)
    ml_confidence: str = "ML: Ready"
    ml_model_info: MLModelInfo = field(default_factory=MLModelInfo.detect_model)

    @classmethod
    def from_state(
        cls,
        *,
        total_damage: int,
        rolling_dps: float,
        biggest_hit: int,
        last_hit: int | None,
        status: str,
        recent_hits: list[str] | None = None,
        ml_model_info: MLModelInfo | None = None,
    ) -> "PreviewViewModel":
        last_hit_label = (
            "No hit yet" if last_hit is None else format_damage_value(last_hit)
        )
        model_info = ml_model_info or MLModelInfo.detect_model()
        return cls(
            total_damage_label=format_damage_value(total_damage),
            rolling_dps_label=format_damage_value(rolling_dps),
            biggest_hit_label=format_damage_value(biggest_hit),
            last_hit_label=last_hit_label,
            status_label=status,
            recent_hits=recent_hits or [],
            ml_model_info=model_info,
        )
