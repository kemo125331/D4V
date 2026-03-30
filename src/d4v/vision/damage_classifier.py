"""Damage type classification for detected hits.

Classifies damage into types:
- Direct: Standard direct damage
- Crit: Critical hits (larger font, gold color)
- DoT: Damage over time ticks (small, rapid)
- Shield: Shield gain (blue, shield icon)
- Healing: Healing received (green, heart icon)
- Resource: Resource gain (mana, spirit)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from d4v.vision.enhanced_color_mask import DamageColor


class DamageType(StrEnum):
    """Damage/effect type classification."""

    DIRECT = "direct"
    CRIT = "crit"
    DOT_TICK = "dot_tick"
    SHIELD_GAIN = "shield_gain"
    HEALING = "healing"
    RESOURCE_GAIN = "resource_gain"
    GOLD_GAIN = "gold_gain"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ClassifiedDamage:
    """Classified damage hit.

    Attributes:
        value: Damage/effect value.
        damage_type: Classified damage type.
        confidence: Classification confidence (0-1).
        color_hint: Detected color type.
        size_hint: Size classification (small/normal/large).
        features: Features used for classification.
    """

    value: int
    damage_type: DamageType
    confidence: float
    color_hint: DamageColor | None = None
    size_hint: str = "normal"
    features: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "value": self.value,
            "damage_type": str(self.damage_type),
            "confidence": round(self.confidence, 4),
            "color_hint": str(self.color_hint) if self.color_hint else None,
            "size_hint": self.size_hint,
            "features": self.features,
        }


class DamageTypeClassifier:
    """Classifier for damage types.

    Uses multiple features for classification:
    - Color (from enhanced color mask)
    - Size (bounding box dimensions)
    - Value patterns
    - Temporal patterns (for DoT)

    Example:
        classifier = DamageTypeClassifier()

        classified = classifier.classify(
            value=1234,
            width=80,
            height=24,
            color_type=DamageColor.YELLOW_ORANGE,
            confidence=0.85,
        )

        print(f"Type: {classified.damage_type}")
        print(f"Confidence: {classified.confidence}")
    """

    # Size thresholds (pixels)
    SMALL_HEIGHT_MAX = 20
    LARGE_HEIGHT_MIN = 32

    # Value thresholds
    DOT_VALUE_MAX = 500
    CRIT_VALUE_MIN = 5000

    def __init__(
        self,
        use_temporal_features: bool = True,
        dot_window_frames: int = 10,
        dot_tick_interval: int = 3,
    ) -> None:
        """Initialize damage type classifier.

        Args:
            use_temporal_features: Use temporal patterns for DoT detection.
            dot_window_frames: Frames to track for DoT pattern.
            dot_tick_interval: Expected DoT tick interval in frames.
        """
        self.use_temporal_features = use_temporal_features
        self.dot_window_frames = dot_window_frames
        self.dot_tick_interval = dot_tick_interval

        # Track recent hits for temporal analysis
        self.recent_hits: list[dict[str, Any]] = []

    def classify(
        self,
        value: int,
        width: int,
        height: int,
        color_type: DamageColor | None = None,
        confidence: float = 0.5,
        raw_text: str = "",
        center_x: float = 0.0,
        center_y: float = 0.0,
        frame_index: int = 0,
    ) -> ClassifiedDamage:
        """Classify a damage hit.

        Args:
            value: Damage value.
            width: Bounding box width.
            height: Bounding box height.
            color_type: Detected color type.
            confidence: Detection confidence.
            raw_text: Raw OCR text.
            center_x: X coordinate of center.
            center_y: Y coordinate of center.
            frame_index: Frame index.

        Returns:
            ClassifiedDamage object.
        """
        # Extract features
        features = self._extract_features(
            value=value,
            width=width,
            height=height,
            color_type=color_type,
            confidence=confidence,
            raw_text=raw_text,
            center_x=center_x,
            center_y=center_y,
            frame_index=frame_index,
        )

        # Classify based on features
        damage_type, type_confidence = self._classify_from_features(features)

        # Determine size hint
        size_hint = self._get_size_hint(height)

        # Update recent hits for temporal analysis
        if self.use_temporal_features:
            self._update_recent_hits(features)

        return ClassifiedDamage(
            value=value,
            damage_type=damage_type,
            confidence=type_confidence,
            color_hint=color_type,
            size_hint=size_hint,
            features=features,
        )

    def _extract_features(
        self,
        value: int,
        width: int,
        height: int,
        color_type: DamageColor | None,
        confidence: float,
        raw_text: str,
        center_x: float,
        center_y: float,
        frame_index: int,
    ) -> dict[str, Any]:
        """Extract features for classification.

        Args:
            value: Damage value.
            width: Bounding box width.
            height: Bounding box height.
            color_type: Detected color type.
            confidence: Detection confidence.
            raw_text: Raw OCR text.
            center_x: X coordinate.
            center_y: Y coordinate.
            frame_index: Frame index.

        Returns:
            Feature dictionary.
        """
        # Size features
        aspect_ratio = width / max(height, 1)
        area = width * height

        # Value features
        has_suffix = any(c in raw_text.upper() for c in "KMB") if raw_text else False
        has_decimal = "." in raw_text if raw_text else False

        # Temporal features (if enabled)
        is_dot_pattern = False
        if self.use_temporal_features:
            is_dot_pattern = self._check_dot_pattern(center_x, center_y, frame_index)

        return {
            "value": value,
            "width": width,
            "height": height,
            "aspect_ratio": aspect_ratio,
            "area": area,
            "color_type": color_type,
            "confidence": confidence,
            "has_suffix": has_suffix,
            "has_decimal": has_decimal,
            "is_small": height < self.SMALL_HEIGHT_MAX,
            "is_large": height > self.LARGE_HEIGHT_MIN,
            "is_dot_pattern": is_dot_pattern,
            "center_x": center_x,
            "center_y": center_y,
            "frame_index": frame_index,
        }

    def _classify_from_features(
        self,
        features: dict[str, Any],
    ) -> tuple[DamageType, float]:
        """Classify damage type from features.

        Args:
            features: Feature dictionary.

        Returns:
            Tuple of (DamageType, confidence).
        """
        color = features.get("color_type")
        height = features.get("height", 24)
        value = features.get("value", 0)
        is_dot_pattern = features.get("is_dot_pattern", False)

        # Decision tree for classification

        # Check for gold (gold pickup)
        if color == DamageColor.GOLD:
            return (DamageType.GOLD_GAIN, 0.90)

        # Check for healing (green, typically with heart)
        if color == DamageColor.GREEN and value > 0:
            # Could be poison or healing - healing usually has specific patterns
            if value < 1000:  # Healing tends to be smaller
                return (DamageType.HEALING, 0.75)
            return (DamageType.DOT_TICK, 0.70)

        # Check for shield (blue, specific value patterns)
        if color == DamageColor.BLUE:
            if value < 5000:  # Shields typically smaller
                return (DamageType.SHIELD_GAIN, 0.80)
            return (DamageType.DIRECT, 0.70)

        # Check for crit (large size, gold/yellow)
        if features.get("is_large") or height > self.LARGE_HEIGHT_MIN:
            if color in (DamageColor.GOLD, DamageColor.YELLOW_ORANGE):
                return (DamageType.CRIT, 0.90)
            return (DamageType.CRIT, 0.75)

        # Check for DoT pattern (rapid ticks at same position)
        if is_dot_pattern:
            return (DamageType.DOT_TICK, 0.85)

        # Check for small values (likely DoT ticks)
        if features.get("is_small") and value < self.DOT_VALUE_MAX:
            return (DamageType.DOT_TICK, 0.70)

        # Default: direct damage
        return (DamageType.DIRECT, 0.65)

    def _get_size_hint(self, height: int) -> str:
        """Get size classification.

        Args:
            height: Bounding box height.

        Returns:
            Size hint string.
        """
        if height < self.SMALL_HEIGHT_MAX:
            return "small"
        elif height > self.LARGE_HEIGHT_MIN:
            return "large"
        return "normal"

    def _check_dot_pattern(
        self,
        center_x: float,
        center_y: float,
        frame_index: int,
    ) -> bool:
        """Check if hit matches DoT tick pattern.

        Args:
            center_x: X coordinate.
            center_y: Y coordinate.
            frame_index: Frame index.

        Returns:
            True if matches DoT pattern.
        """
        if not self.recent_hits:
            return False

        # Check for hits at similar position
        for recent in self.recent_hits[-10:]:
            dx = abs(recent.get("center_x", 0) - center_x)
            dy = abs(recent.get("center_y", 0) - center_y)

            # Same position (within 30 pixels)
            if dx < 30 and dy < 30:
                # Check timing (DoT ticks every ~1 second = 30 frames)
                frame_diff = frame_index - recent.get("frame_index", 0)
                if 20 <= frame_diff <= 40:  # ~20-40 frames
                    return True

        return False

    def _update_recent_hits(self, features: dict[str, Any]) -> None:
        """Update recent hits for temporal analysis.

        Args:
            features: Current hit features.
        """
        self.recent_hits.append(features)

        # Limit history
        max_history = self.dot_window_frames * 2
        if len(self.recent_hits) > max_history:
            self.recent_hits = self.recent_hits[-max_history:]

    def classify_batch(
        self,
        hits: list[dict[str, Any]],
    ) -> list[ClassifiedDamage]:
        """Classify multiple hits.

        Args:
            hits: List of hit dictionaries.

        Returns:
            List of ClassifiedDamage objects.
        """
        results: list[ClassifiedDamage] = []

        for hit in hits:
            classified = self.classify(**hit)
            results.append(classified)

        return results

    def get_type_statistics(
        self,
        classified_hits: list[ClassifiedDamage],
    ) -> dict[str, Any]:
        """Get statistics for classified hits.

        Args:
            classified_hits: List of classified hits.

        Returns:
            Statistics dictionary.
        """
        type_counts: dict[str, int] = {}
        type_values: dict[str, list[int]] = {}

        for hit in classified_hits:
            type_str = str(hit.damage_type)
            type_counts[type_str] = type_counts.get(type_str, 0) + 1
            type_values.setdefault(type_str, []).append(hit.value)

        # Calculate averages
        type_averages: dict[str, float] = {}
        for type_str, values in type_values.items():
            type_averages[type_str] = sum(values) / len(values) if values else 0.0

        return {
            "total_hits": len(classified_hits),
            "type_counts": type_counts,
            "type_averages": type_averages,
            "type_percentages": {
                t: c / len(classified_hits) if classified_hits else 0
                for t, c in type_counts.items()
            },
        }

    def reset(self) -> None:
        """Reset classifier state."""
        self.recent_hits.clear()


def classify_damage_type(
    value: int,
    width: int,
    height: int,
    color_type: str | None = None,
    confidence: float = 0.5,
) -> ClassifiedDamage:
    """Convenience function for damage classification.

    Args:
        value: Damage value.
        width: Bounding box width.
        height: Bounding box height.
        color_type: Color type string.
        confidence: Detection confidence.

    Returns:
        ClassifiedDamage object.
    """
    classifier = DamageTypeClassifier()

    # Convert color string to enum
    color_enum = None
    if color_type:
        try:
            color_enum = DamageColor(color_type)
        except ValueError:
            pass

    return classifier.classify(
        value=value,
        width=width,
        height=height,
        color_type=color_enum,
        confidence=confidence,
    )
