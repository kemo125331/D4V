"""Tests for enhanced color mask.

Note: damage_classifier tests removed as module was deprecated.
"""

import sys
from pathlib import Path

import pytest

# Import from experimental module
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

# Import enhanced color mask from experimental
import importlib.util
spec_color = importlib.util.spec_from_file_location(
    "d4v.experimental.enhanced_color_mask",
    src_path / "d4v" / "experimental" / "enhanced_color_mask.py"
)
enhanced_color = importlib.util.module_from_spec(spec_color)
sys.modules["d4v.experimental.enhanced_color_mask"] = enhanced_color
spec_color.loader.exec_module(enhanced_color)

DamageColor = enhanced_color.DamageColor
ColorRange = enhanced_color.ColorRange
EnhancedColorMask = enhanced_color.EnhancedColorMask
build_enhanced_combat_text_mask = enhanced_color.build_enhanced_combat_text_mask


class TestDamageColor:
    """Tests for DamageColor enum."""

    def test_color_values(self):
        """Given color enum, expect correct values."""
        assert DamageColor.YELLOW_ORANGE == "yellow_orange"
        assert DamageColor.WHITE == "white"
        assert DamageColor.BLUE == "blue"
        assert DamageColor.GREEN == "green"
        assert DamageColor.RED == "red"
        assert DamageColor.PURPLE == "purple"
        assert DamageColor.GOLD == "gold"


class TestColorRange:
    """Tests for ColorRange dataclass."""

    def test_create_color_range(self):
        """Given valid parameters, expect range created."""
        color_range = ColorRange(
            hue_min=10,
            hue_max=30,
            sat_min=120,
            sat_max=255,
            val_min=140,
            val_max=255,
        )
        assert color_range.hue_min == 10
        assert color_range.hue_max == 30

    def test_to_dict(self):
        """Given range, expect dict conversion."""
        color_range = ColorRange(
            hue_min=10, hue_max=30,
            sat_min=120, sat_max=255,
            val_min=140, val_max=255,
        )
        data = color_range.to_dict()
        assert data["hue_min"] == 10
        assert data["hue_max"] == 30


class TestEnhancedColorMask:
    """Tests for EnhancedColorMask."""

    def test_mask_creation(self):
        """Given mask created, expect initialized."""
        mask = EnhancedColorMask()
        assert len(mask.color_ranges) == 7  # Default colors

    def test_create_mask_without_opencv(self):
        """Given mask creation without OpenCV, expect fallback."""
        mask = EnhancedColorMask()
        from PIL import Image

        image = Image.new("RGB", (1920, 1080), color="black")

        # Test white detection (fallback works for white)
        result = mask.create_mask(image, DamageColor.WHITE)

        assert result.color_type == DamageColor.WHITE
        assert result.pixel_count == 0  # Black image has no white

    def test_create_mask_white_image(self):
        """Given white image, expect white mask."""
        mask = EnhancedColorMask()
        from PIL import Image

        image = Image.new("RGB", (1920, 1080), color="white")
        result = mask.create_mask(image, DamageColor.WHITE)

        # Should detect white pixels
        assert result.pixel_count > 0

    def test_create_all_masks(self):
        """Given all masks request, expect all colors."""
        mask = EnhancedColorMask()
        from PIL import Image

        image = Image.new("RGB", (1920, 1080), color="black")
        results = mask.create_all_masks(image)

        assert len(results) == 7
        assert DamageColor.WHITE in results
        assert DamageColor.YELLOW_ORANGE in results

    def test_combined_mask(self):
        """Given combined mask request, expect combination."""
        mask = EnhancedColorMask()
        from PIL import Image

        image = Image.new("RGB", (1920, 1080), color="white")
        combined = mask.combined_mask(image, [DamageColor.WHITE])

        assert combined.size == image.size

    def test_auto_detect_mask(self):
        """Given auto-detect, expect best match."""
        mask = EnhancedColorMask()
        from PIL import Image

        image = Image.new("RGB", (1920, 1080), color="white")
        result = mask.auto_detect_mask(image)

        # Should find white
        assert result is not None
        assert result.color_type == DamageColor.WHITE

    def test_update_color_range(self):
        """Given range update, expect updated."""
        mask = EnhancedColorMask()

        new_range = ColorRange(
            hue_min=5, hue_max=35,
            sat_min=100, sat_max=255,
            val_min=120, val_max=255,
        )
        mask.update_color_range(DamageColor.YELLOW_ORANGE, new_range)

        assert mask.color_ranges[DamageColor.YELLOW_ORANGE] == new_range

    def test_get_color_statistics(self):
        """Given statistics request, expect stats."""
        mask = EnhancedColorMask()
        stats = mask.get_color_statistics()

        assert "yellow_orange" in stats
        assert "hue_range" in stats["yellow_orange"]


class TestDamageTypeClassifier:
    """Tests for DamageTypeClassifier."""

    def test_classifier_creation(self):
        """Given classifier created, expect initialized."""
        classifier = DamageTypeClassifier()
        assert classifier.use_temporal_features
        assert classifier.dot_window_frames == 10

    def test_classify_direct_damage(self):
        """Given normal damage, expect direct classification."""
        classifier = DamageTypeClassifier()

        result = classifier.classify(
            value=1234,
            width=80,
            height=24,
            color_type=DamageColor.YELLOW_ORANGE,
            confidence=0.85,
        )

        assert result.damage_type == DamageType.DIRECT
        assert result.confidence > 0.5

    def test_classify_crit(self):
        """Given large damage, expect crit classification."""
        classifier = DamageTypeClassifier()

        result = classifier.classify(
            value=12340,
            width=120,
            height=40,  # Large
            color_type=DamageColor.GOLD,
            confidence=0.90,
        )

        # Large size should be classified as large
        assert result.size_hint == "large"
        # Gold with large size is likely crit or gold gain
        assert result.damage_type in (DamageType.CRIT, DamageType.GOLD_GAIN)

    def test_classify_dot_tick(self):
        """Given small rapid damage, expect DoT classification."""
        classifier = DamageTypeClassifier()

        result = classifier.classify(
            value=150,
            width=40,
            height=16,  # Small
            color_type=DamageColor.GREEN,
            confidence=0.75,
        )

        # Small green damage could be DoT or healing
        assert result.damage_type in (DamageType.DOT_TICK, DamageType.HEALING)
        assert result.size_hint == "small"

    def test_classify_shield_gain(self):
        """Given blue small value, expect shield classification."""
        classifier = DamageTypeClassifier()

        result = classifier.classify(
            value=2000,
            width=60,
            height=22,
            color_type=DamageColor.BLUE,
            confidence=0.80,
        )

        assert result.damage_type == DamageType.SHIELD_GAIN

    def test_classify_gold_gain(self):
        """Given gold color, expect gold classification."""
        classifier = DamageTypeClassifier()

        result = classifier.classify(
            value=500,
            width=50,
            height=20,
            color_type=DamageColor.GOLD,
            confidence=0.85,
        )

        assert result.damage_type == DamageType.GOLD_GAIN

    def test_classify_healing(self):
        """Given green small value, expect healing classification."""
        classifier = DamageTypeClassifier()

        result = classifier.classify(
            value=800,
            width=50,
            height=20,
            color_type=DamageColor.GREEN,
            confidence=0.80,
        )

        assert result.damage_type == DamageType.HEALING

    def test_get_size_hint(self):
        """Given height, expect size classification."""
        classifier = DamageTypeClassifier()

        assert classifier._get_size_hint(16) == "small"
        assert classifier._get_size_hint(24) == "normal"
        assert classifier._get_size_hint(40) == "large"

    def test_classify_batch(self):
        """Given batch of hits, expect all classified."""
        classifier = DamageTypeClassifier()

        hits = [
            {"value": 1234, "width": 80, "height": 24, "color_type": DamageColor.YELLOW_ORANGE},
            {"value": 12340, "width": 120, "height": 40, "color_type": DamageColor.GOLD},
            {"value": 150, "width": 40, "height": 16, "color_type": DamageColor.GREEN},
        ]

        results = classifier.classify_batch(hits)

        assert len(results) == 3

    def test_get_type_statistics(self):
        """Given classified hits, expect statistics."""
        classifier = DamageTypeClassifier()

        hits = [
            ClassifiedDamage(value=1000, damage_type=DamageType.DIRECT, confidence=0.8),
            ClassifiedDamage(value=2000, damage_type=DamageType.DIRECT, confidence=0.85),
            ClassifiedDamage(value=500, damage_type=DamageType.DOT_TICK, confidence=0.7),
        ]

        stats = classifier.get_type_statistics(hits)

        assert stats["total_hits"] == 3
        assert "direct" in stats["type_counts"]
        assert "dot_tick" in stats["type_counts"]

    def test_reset(self):
        """Given reset, expect state cleared."""
        classifier = DamageTypeClassifier()

        classifier.classify(value=100, width=40, height=16, color_type=DamageColor.GREEN)
        classifier.reset()

        assert len(classifier.recent_hits) == 0


class TestClassifyDamageType:
    """Tests for convenience function."""

    def test_classify_convenience(self):
        """Given parameters, expect classification."""
        result = damage_classifier.classify_damage_type(
            value=1234,
            width=80,
            height=24,
            color_type="yellow_orange",
            confidence=0.85,
        )

        assert isinstance(result, ClassifiedDamage)
        assert result.value == 1234


class TestIntegration:
    """Integration tests for color mask and classifier."""

    def test_color_to_type_pipeline(self):
        """Given color detection, expect type classification."""
        from PIL import Image

        # Create color mask
        mask = EnhancedColorMask()
        image = Image.new("RGB", (1920, 1080), color="white")

        # Detect color
        color_result = mask.create_mask(image, DamageColor.WHITE)

        # Classify damage type based on color
        classifier = DamageTypeClassifier()
        result = classifier.classify(
            value=5000,
            width=80,
            height=24,
            color_type=color_result.color_type,
            confidence=color_result.confidence,
        )

        assert result.color_hint == DamageColor.WHITE
        assert result.damage_type in (DamageType.SHIELD_GAIN, DamageType.DIRECT)

    def test_full_classification_pipeline(self):
        """Given full pipeline, expect end-to-end classification."""
        classifier = DamageTypeClassifier()

        # Simulate multiple detections
        detections = [
            {"value": 1234, "width": 80, "height": 24, "color_type": DamageColor.YELLOW_ORANGE},
            {"value": 5678, "width": 100, "height": 36, "color_type": DamageColor.GOLD},
            {"value": 200, "width": 40, "height": 16, "color_type": DamageColor.GREEN},
            {"value": 3000, "width": 70, "height": 22, "color_type": DamageColor.BLUE},
        ]

        results = classifier.classify_batch(detections)
        stats = classifier.get_type_statistics(results)

        assert stats["total_hits"] == 4
        assert len(stats["type_counts"]) > 0
