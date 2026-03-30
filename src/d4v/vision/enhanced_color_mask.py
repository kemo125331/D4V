"""Enhanced color segmentation for multiple damage types.

Supports detection of various damage number colors including:
- Yellow/Orange (standard damage)
- White (normal text)
- Blue (freeze/cold damage)
- Green (poison/nature damage)
- Red (fire damage)
- Purple (lightning/arcane damage)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Literal

from PIL import Image


class DamageColor(StrEnum):
    """Damage number color types."""

    YELLOW_ORANGE = "yellow_orange"  # Standard damage
    WHITE = "white"  # Normal text, healing
    BLUE = "blue"  # Freeze/cold
    GREEN = "green"  # Poison/nature
    RED = "red"  # Fire
    PURPLE = "purple"  # Lightning/arcane
    GOLD = "gold"  # Critical hits, rare


@dataclass(frozen=True)
class ColorRange:
    """HSV color range for damage detection.

    Attributes:
        hue_min: Minimum hue value (0-180).
        hue_max: Maximum hue value (0-180).
        sat_min: Minimum saturation (0-255).
        sat_max: Maximum saturation (0-255).
        val_min: Minimum value/brightness (0-255).
        val_max: Maximum value/brightness (0-255).
    """

    hue_min: int
    hue_max: int
    sat_min: int
    sat_max: int
    val_min: int
    val_max: int

    def to_dict(self) -> dict[str, int]:
        """Convert to dictionary."""
        return {
            "hue_min": self.hue_min,
            "hue_max": self.hue_max,
            "sat_min": self.sat_min,
            "sat_max": self.sat_max,
            "val_min": self.val_min,
            "val_max": self.val_max,
        }


# Default color ranges for damage types
DEFAULT_COLOR_RANGES: dict[DamageColor, ColorRange] = {
    DamageColor.YELLOW_ORANGE: ColorRange(
        hue_min=10, hue_max=30,
        sat_min=120, sat_max=255,
        val_min=140, val_max=255,
    ),
    DamageColor.WHITE: ColorRange(
        hue_min=0, hue_max=180,
        sat_min=0, sat_max=40,
        val_min=190, val_max=255,
    ),
    DamageColor.BLUE: ColorRange(
        hue_min=90, hue_max=130,
        sat_min=100, sat_max=255,
        val_min=140, val_max=255,
    ),
    DamageColor.GREEN: ColorRange(
        hue_min=50, hue_max=70,
        sat_min=100, sat_max=255,
        val_min=140, val_max=255,
    ),
    DamageColor.RED: ColorRange(
        hue_min=0, hue_max=10,
        sat_min=150, sat_max=255,
        val_min=140, val_max=255,
    ),
    DamageColor.PURPLE: ColorRange(
        hue_min=130, hue_max=160,
        sat_min=80, sat_max=255,
        val_min=140, val_max=255,
    ),
    DamageColor.GOLD: ColorRange(
        hue_min=25, hue_max=35,
        sat_min=150, sat_max=255,
        val_min=180, val_max=255,
    ),
}


@dataclass(frozen=True)
class ColorMaskResult:
    """Result of color masking operation.

    Attributes:
        mask: Binary mask image.
        color_type: Damage color type detected.
        pixel_count: Number of pixels in mask.
        confidence: Confidence in color classification.
    """

    mask: Image.Image
    color_type: DamageColor
    pixel_count: int
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "color_type": str(self.color_type),
            "pixel_count": self.pixel_count,
            "confidence": round(self.confidence, 4),
        }


class EnhancedColorMask:
    """Enhanced color masking for multiple damage types.

    Example:
        mask = EnhancedColorMask()

        # Create mask for specific color
        result = mask.create_mask(image, DamageColor.YELLOW_ORANGE)

        # Create masks for all colors
        all_masks = mask.create_all_masks(image)

        # Auto-detect best color
        result = mask.auto_detect_mask(image)
    """

    def __init__(
        self,
        color_ranges: dict[DamageColor, ColorRange] | None = None,
    ) -> None:
        """Initialize enhanced color mask.

        Args:
            color_ranges: Custom color ranges. Uses defaults if None.
        """
        self.color_ranges = color_ranges or DEFAULT_COLOR_RANGES.copy()

    def create_mask(
        self,
        image: Image.Image,
        color_type: DamageColor,
    ) -> ColorMaskResult:
        """Create binary mask for specific color type.

        Args:
            image: Input PIL Image (RGB).
            color_type: Damage color to detect.

        Returns:
            ColorMaskResult with mask and statistics.
        """
        try:
            import cv2
            import numpy as np
        except ImportError:
            # Fallback without OpenCV
            return self._create_mask_fallback(image, color_type)

        # Convert to HSV
        rgb = image.convert("RGB")
        bgr = cv2.cvtColor(np.array(rgb), cv2.COLOR_RGB2BGR)
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

        # Get color range
        color_range = self.color_ranges.get(color_type)
        if color_range is None:
            # Return empty mask
            from PIL import Image
            empty_mask = Image.new("L", image.size, 0)
            return ColorMaskResult(
                mask=empty_mask,
                color_type=color_type,
                pixel_count=0,
                confidence=0.0,
            )

        # Create mask
        lower = np.array([color_range.hue_min, color_range.sat_min, color_range.val_min])
        upper = np.array([color_range.hue_max, color_range.sat_max, color_range.val_max])
        mask_arr = cv2.inRange(hsv, lower, upper)

        # Count pixels
        pixel_count = int(np.count_nonzero(mask_arr))

        # Convert to PIL
        mask_img = Image.fromarray(mask_arr, mode="L")

        # Calculate confidence based on color match quality
        confidence = self._calculate_confidence(mask_arr, color_type)

        return ColorMaskResult(
            mask=mask_img,
            color_type=color_type,
            pixel_count=pixel_count,
            confidence=confidence,
        )

    def _create_mask_fallback(
        self,
        image: Image.Image,
        color_type: DamageColor,
    ) -> ColorMaskResult:
        """Create mask without OpenCV (fallback).

        Args:
            image: Input PIL Image.
            color_type: Damage color to detect.

        Returns:
            ColorMaskResult with basic mask.
        """
        from PIL import Image
        import numpy as np

        # Convert to RGB
        rgb = image.convert("RGB")
        arr = np.array(rgb)

        # Get color range
        color_range = self.color_ranges.get(color_type)
        if color_range is None:
            empty_mask = Image.new("L", image.size, 0)
            return ColorMaskResult(
                mask=empty_mask,
                color_type=color_type,
                pixel_count=0,
                confidence=0.0,
            )

        # Simple RGB-based masking (less accurate than HSV)
        r = arr[:, :, 0]
        g = arr[:, :, 1]
        b = arr[:, :, 2]

        # Approximate HSV ranges in RGB
        if color_type == DamageColor.WHITE:
            mask_arr = ((r > 190) & (g > 190) & (b > 190)).astype(np.uint8) * 255
        elif color_type == DamageColor.RED:
            mask_arr = ((r > 150) & (g < 100) & (b < 100)).astype(np.uint8) * 255
        elif color_type == DamageColor.GREEN:
            mask_arr = ((r < 100) & (g > 150) & (b < 100)).astype(np.uint8) * 255
        elif color_type == DamageColor.BLUE:
            mask_arr = ((r < 100) & (g < 100) & (b > 150)).astype(np.uint8) * 255
        else:
            mask_arr = np.zeros_like(r, dtype=np.uint8)

        pixel_count = int(np.count_nonzero(mask_arr))
        mask_img = Image.fromarray(mask_arr, mode="L")

        return ColorMaskResult(
            mask=mask_img,
            color_type=color_type,
            pixel_count=pixel_count,
            confidence=0.5 if pixel_count > 0 else 0.0,
        )

    def create_all_masks(
        self,
        image: Image.Image,
    ) -> dict[DamageColor, ColorMaskResult]:
        """Create masks for all color types.

        Args:
            image: Input PIL Image.

        Returns:
            Dictionary mapping color types to results.
        """
        results: dict[DamageColor, ColorMaskResult] = {}

        for color_type in self.color_ranges.keys():
            results[color_type] = self.create_mask(image, color_type)

        return results

    def auto_detect_mask(
        self,
        image: Image.Image,
        min_pixels: int = 100,
    ) -> ColorMaskResult | None:
        """Auto-detect best color mask for image.

        Args:
            image: Input PIL Image.
            min_pixels: Minimum pixels for valid detection.

        Returns:
            Best ColorMaskResult or None.
        """
        results = self.create_all_masks(image)

        # Find best result with sufficient pixels
        best_result: ColorMaskResult | None = None
        best_score = 0.0

        for result in results.values():
            if result.pixel_count < min_pixels:
                continue

            # Score by pixel count and confidence
            score = result.pixel_count * result.confidence

            if score > best_score:
                best_score = score
                best_result = result

        return best_result

    def combined_mask(
        self,
        image: Image.Image,
        color_types: list[DamageColor] | None = None,
    ) -> Image.Image:
        """Create combined mask for multiple color types.

        Args:
            image: Input PIL Image.
            color_types: Color types to include. All if None.

        Returns:
            Combined binary mask.
        """
        try:
            import cv2
            import numpy as np
        except ImportError:
            return self._combined_mask_fallback(image, color_types)

        color_types = color_types or list(self.color_ranges.keys())

        combined: list[Any] = []

        for color_type in color_types:
            result = self.create_mask(image, color_type)
            combined.append(cv2.cvtColor(np.array(result.mask), cv2.COLOR_GRAY2BGR))

        if not combined:
            return Image.new("L", image.size, 0)

        # Combine masks
        result_mask = combined[0]
        for mask in combined[1:]:
            result_mask = cv2.bitwise_or(result_mask, mask)

        # Convert to grayscale
        result_gray = cv2.cvtColor(result_mask, cv2.COLOR_BGR2GRAY)

        return Image.fromarray(result_gray, mode="L")

    def _combined_mask_fallback(
        self,
        image: Image.Image,
        color_types: list[DamageColor] | None = None,
    ) -> Image.Image:
        """Fallback combined mask without OpenCV."""
        from PIL import Image
        import numpy as np

        color_types = color_types or list(self.color_ranges.keys())

        combined = np.zeros((image.height, image.width), dtype=np.uint8)

        for color_type in color_types:
            result = self.create_mask(image, color_type)
            combined = np.maximum(combined, np.array(result.mask))

        return Image.fromarray(combined, mode="L")

    def _calculate_confidence(
        self,
        mask_arr: Any,
        color_type: DamageColor,
    ) -> float:
        """Calculate confidence score for mask.

        Args:
            mask_arr: Numpy array of mask.
            color_type: Color type detected.

        Returns:
            Confidence score (0-1).
        """
        import numpy as np

        pixel_count = np.count_nonzero(mask_arr)
        total_pixels = mask_arr.size

        if pixel_count == 0:
            return 0.0

        # Base confidence on fill ratio
        fill_ratio = pixel_count / total_pixels

        # Optimal fill ratio is 1-10% for damage numbers
        if 0.01 <= fill_ratio <= 0.10:
            ratio_score = 1.0
        elif fill_ratio < 0.01:
            ratio_score = fill_ratio / 0.01
        else:
            ratio_score = max(0, 1.0 - (fill_ratio - 0.10) / 0.40)

        # Color-specific adjustments
        color_confidence = {
            DamageColor.YELLOW_ORANGE: 0.95,  # Most common
            DamageColor.WHITE: 0.85,
            DamageColor.BLUE: 0.90,
            DamageColor.GREEN: 0.85,
            DamageColor.RED: 0.85,
            DamageColor.PURPLE: 0.80,
            DamageColor.GOLD: 0.90,
        }

        return ratio_score * color_confidence.get(color_type, 0.8)

    def update_color_range(
        self,
        color_type: DamageColor,
        color_range: ColorRange,
    ) -> None:
        """Update color range for specific type.

        Args:
            color_type: Color type to update.
            color_range: New color range.
        """
        self.color_ranges[color_type] = color_range

    def calibrate_from_sample(
        self,
        sample_image: Image.Image,
        sample_region: tuple[int, int, int, int],
        color_type: DamageColor,
    ) -> ColorRange:
        """Calibrate color range from sample region.

        Args:
            sample_image: Image containing sample color.
            sample_region: (left, top, right, bottom) of sample.
            color_type: Expected color type.

        Returns:
            Calibrated ColorRange.
        """
        try:
            import cv2
            import numpy as np
        except ImportError:
            return self.color_ranges.get(color_type, DEFAULT_COLOR_RANGES[color_type])

        # Extract sample region
        rgb = sample_image.convert("RGB").crop(sample_region)
        bgr = cv2.cvtColor(np.array(rgb), cv2.COLOR_RGB2BGR)
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

        # Calculate statistics
        h_mean = np.mean(hsv[:, :, 0])
        h_std = np.std(hsv[:, :, 0])
        s_mean = np.mean(hsv[:, :, 1])
        s_std = np.std(hsv[:, :, 1])
        v_mean = np.mean(hsv[:, :, 2])
        v_std = np.std(hsv[:, :, 2])

        # Create calibrated range
        calibrated = ColorRange(
            hue_min=max(0, int(h_mean - 2 * h_std)),
            hue_max=min(180, int(h_mean + 2 * h_std)),
            sat_min=max(0, int(s_mean - 2 * s_std)),
            sat_max=min(255, int(s_mean + 2 * s_std)),
            val_min=max(0, int(v_mean - 2 * v_std)),
            val_max=min(255, int(v_mean + 2 * v_std)),
        )

        # Update stored range
        self.color_ranges[color_type] = calibrated

        return calibrated

    def get_color_statistics(self) -> dict[str, Any]:
        """Get statistics about configured color ranges.

        Returns:
            Dictionary of color statistics.
        """
        stats: dict[str, Any] = {}

        for color_type, color_range in self.color_ranges.items():
            stats[str(color_type)] = {
                "hue_range": (color_range.hue_min, color_range.hue_max),
                "sat_range": (color_range.sat_min, color_range.sat_max),
                "val_range": (color_range.val_min, color_range.val_max),
                "hue_width": color_range.hue_max - color_range.hue_min,
            }

        return stats


def build_enhanced_combat_text_mask(
    image: Image.Image,
    enabled_colors: list[DamageColor] | None = None,
) -> Image.Image:
    """Build enhanced combat text mask with multiple colors.

    Args:
        image: Input PIL Image (RGB).
        enabled_colors: Colors to detect. All if None.

    Returns:
        Combined binary mask.
    """
    mask = EnhancedColorMask()
    return mask.combined_mask(image, enabled_colors)


def count_damage_color_pixels(
    image: Image.Image,
    color_type: DamageColor,
) -> int:
    """Count pixels of specific damage color.

    Args:
        image: Input PIL Image.
        color_type: Color to count.

    Returns:
        Pixel count.
    """
    mask = EnhancedColorMask()
    result = mask.create_mask(image, color_type)
    return result.pixel_count
