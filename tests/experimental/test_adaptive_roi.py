"""Tests for adaptive ROI tracking."""

import sys
from pathlib import Path

import pytest

# Import from experimental module
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

import importlib.util
spec = importlib.util.spec_from_file_location(
    "d4v.experimental.adaptive_roi",
    src_path / "d4v" / "experimental" / "adaptive_roi.py"
)
adaptive_roi = importlib.util.module_from_spec(spec)
sys.modules["d4v.experimental.adaptive_roi"] = adaptive_roi
spec.loader.exec_module(adaptive_roi)

AdaptiveRoiTracker = adaptive_roi.AdaptiveRoiTracker
AdaptiveRoiState = adaptive_roi.AdaptiveRoiState
MotionDetector = adaptive_roi.MotionDetector
MotionRegion = adaptive_roi.MotionRegion
RoiPredictor = adaptive_roi.RoiPredictor


class TestMotionRegion:
    """Tests for MotionRegion dataclass."""

    def test_create_motion_region(self):
        """Given valid parameters, expect region created."""
        region = MotionRegion(
            x=500.0,
            y=300.0,
            width=100,
            height=50,
            motion_score=0.8,
            frame=10,
        )
        assert region.x == 500.0
        assert region.motion_score == 0.8

    def test_to_dict(self):
        """Given region, expect dict conversion."""
        region = MotionRegion(
            x=500.0,
            y=300.0,
            width=100,
            height=50,
            motion_score=0.8,
            frame=10,
        )
        data = region.to_dict()
        assert data["x"] == 500.0
        assert data["width"] == 100


class TestAdaptiveRoiState:
    """Tests for AdaptiveRoiState dataclass."""

    def test_create_state(self):
        """Given valid parameters, expect state created."""
        state = AdaptiveRoiState(
            left=100,
            top=50,
            right=800,
            bottom=600,
        )
        assert state.left == 100
        assert state.width == 700
        assert state.height == 550

    def test_to_tuple(self):
        """Given state, expect tuple conversion."""
        state = AdaptiveRoiState(
            left=100,
            top=50,
            right=800,
            bottom=600,
        )
        result = state.to_tuple()
        assert result == (100, 50, 800, 600)

    def test_to_dict(self):
        """Given state, expect dict conversion."""
        state = AdaptiveRoiState(
            left=100,
            top=50,
            right=800,
            bottom=600,
            expansion_reason="motion_detected",
            confidence=0.8,
        )
        data = state.to_dict()
        assert data["expansion_reason"] == "motion_detected"
        assert data["confidence"] == 0.8


class TestMotionDetector:
    """Tests for MotionDetector."""

    def test_detector_creation(self):
        """Given detector created, expect initialized."""
        detector = MotionDetector()
        assert detector.threshold == 100
        assert detector.min_region_size == 500

    def test_detect_motion_no_previous(self):
        """Given no previous frame, expect empty regions."""
        detector = MotionDetector()
        from PIL import Image
        current = Image.new("RGB", (1920, 1080), color="black")

        regions = detector.detect_motion(current, None, frame=0)

        assert regions == []

    def test_detect_motion_simple_no_previous(self):
        """Given no previous frame, expect zero motion."""
        detector = MotionDetector()
        from PIL import Image
        current = Image.new("RGB", (1920, 1080), color="black")

        score = detector.detect_motion_simple(current, None)

        assert score == 0.0

    def test_detect_motion_same_frame(self):
        """Given identical frames, expect minimal motion."""
        detector = MotionDetector()
        from PIL import Image
        frame = Image.new("RGB", (1920, 1080), color="black")

        regions = detector.detect_motion(frame, frame, frame=0)

        # Should have minimal or no motion
        assert len(regions) == 0 or all(r.motion_score < 0.1 for r in regions)


class TestAdaptiveRoiTracker:
    """Tests for AdaptiveRoiTracker."""

    def test_tracker_creation(self):
        """Given tracker created, expect initialized."""
        tracker = AdaptiveRoiTracker()
        assert tracker.base_roi == (0.15, 0.05, 0.70, 0.75)
        assert tracker.expansion_margin == 100

    def test_update_no_previous_frame(self):
        """Given no previous frame, expect base ROI."""
        tracker = AdaptiveRoiTracker()
        from PIL import Image
        current = Image.new("RGB", (1920, 1080), color="black")

        state = tracker.update(current, None, frame_index=0)

        assert state.confidence == 1.0
        assert state.expansion_reason == ""

    def test_update_with_motion(self):
        """Given motion detected, expect potential expansion."""
        tracker = AdaptiveRoiTracker()
        from PIL import Image

        # Create frames with difference
        frame1 = Image.new("RGB", (1920, 1080), color="black")
        frame2 = Image.new("RGB", (1920, 1080), color="white")

        state = tracker.update(frame2, frame1, frame_index=1)

        # State should be created
        assert state is not None
        assert isinstance(state, AdaptiveRoiState)

    def test_get_roi_tuple(self):
        """Given image size, expect ROI tuple."""
        tracker = AdaptiveRoiTracker()

        roi = tracker.get_roi_tuple((1920, 1080))

        assert len(roi) == 4
        assert roi[0] >= 0  # left
        assert roi[1] >= 0  # top
        assert roi[2] <= 1920  # right
        assert roi[3] <= 1080  # bottom

    def test_get_predicted_roi(self):
        """Given prediction request, expect predicted ROI."""
        tracker = AdaptiveRoiTracker()

        # First update to establish state
        from PIL import Image
        frame1 = Image.new("RGB", (1920, 1080), color="black")
        frame2 = Image.new("RGB", (1920, 1080), color="black")
        tracker.update(frame2, frame1, frame_index=1)

        predicted = tracker.get_predicted_roi((1920, 1080), frames_ahead=5)

        assert len(predicted) == 4
        assert predicted[0] >= 0

    def test_reset(self):
        """Given reset, expect state cleared."""
        tracker = AdaptiveRoiTracker()

        from PIL import Image
        frame1 = Image.new("RGB", (1920, 1080), color="black")
        frame2 = Image.new("RGB", (1920, 1080), color="white")
        tracker.update(frame2, frame1, frame_index=1)

        tracker.reset()

        assert tracker.current_expansion == 0
        assert tracker.expansion_cooldown == 0

    def test_get_statistics(self):
        """Given statistics request, expect stats."""
        tracker = AdaptiveRoiTracker()

        from PIL import Image
        frame1 = Image.new("RGB", (1920, 1080), color="black")
        frame2 = Image.new("RGB", (1920, 1080), color="black")
        tracker.update(frame2, frame1, frame_index=1)

        stats = tracker.get_statistics()

        assert "current_expansion" in stats
        assert "expansion_cooldown" in stats

    def test_roi_clamping(self):
        """Given expansion, expect ROI clamped to image bounds."""
        tracker = AdaptiveRoiTracker(
            expansion_margin=500,
            max_expansion=500,
        )

        # Force expansion
        tracker.current_expansion = 500

        roi = tracker.get_roi_tuple((1920, 1080))

        assert roi[0] >= 0  # left clamped
        assert roi[1] >= 0  # top clamped
        assert roi[2] <= 1920  # right clamped
        assert roi[3] <= 1080  # bottom clamped


class TestRoiPredictor:
    """Tests for RoiPredictor."""

    def test_predictor_creation(self):
        """Given predictor created, expect initialized."""
        predictor = RoiPredictor()
        assert predictor.history_size == 100
        assert predictor.prediction_frames == 10

    def test_add_position(self):
        """Given position added, expect stored."""
        predictor = RoiPredictor()

        predictor.add_position(frame=10, x=500.0, y=300.0)

        assert len(predictor.position_history) == 1

    def test_predict_spawn_region_no_data(self):
        """Given no data, expect default region."""
        predictor = RoiPredictor()

        region = predictor.predict_spawn_region((1920, 1080))

        assert len(region) == 4
        assert region[0] == int(1920 * 0.15)
        assert region[1] == int(1080 * 0.05)

    def test_predict_spawn_region_with_data(self):
        """Given positions, expect spawn region calculated."""
        predictor = RoiPredictor(history_size=100)

        # Add many positions at consistent location
        for i in range(20):
            predictor.add_position(frame=i, x=600.0, y=400.0)

        region = predictor.predict_spawn_region((1920, 1080))

        assert len(region) == 4
        # Region should include the spawn position
        assert region[0] <= 600
        assert region[1] <= 400

    def test_get_velocity_estimate_no_data(self):
        """Given no data, expect default velocity."""
        predictor = RoiPredictor()

        vx, vy = predictor.get_velocity_estimate()

        assert vx == 0.0
        assert vy == -2.0  # Default upward

    def test_get_velocity_estimate_with_data(self):
        """Given positions, expect velocity calculated."""
        predictor = RoiPredictor()

        # Add positions with upward movement
        for i in range(10):
            predictor.add_position(frame=i, x=500.0, y=400.0 - i * 5)

        vx, vy = predictor.get_velocity_estimate()

        assert abs(vx) < 1.0  # Minimal horizontal
        assert vy < 0  # Upward (negative)

    def test_position_history_limit(self):
        """Given many positions, expect history limited."""
        predictor = RoiPredictor(history_size=50)

        for i in range(100):
            predictor.add_position(frame=i, x=500.0, y=300.0)

        assert len(predictor.position_history) == 50


class TestIntegration:
    """Integration tests for adaptive ROI system."""

    def test_full_tracking_workflow(self):
        """Given full workflow, expect end-to-end tracking."""
        tracker = AdaptiveRoiTracker()
        from PIL import Image

        # Simulate frame sequence
        prev_frame = Image.new("RGB", (1920, 1080), color="black")

        for i in range(10):
            # Create slightly different frames
            curr_frame = Image.new("RGB", (1920, 1080), color=(i * 10, i * 10, i * 10))

            state = tracker.update(curr_frame, prev_frame, frame_index=i)

            assert state is not None
            prev_frame = curr_frame

        # Get final ROI
        roi = tracker.get_roi_tuple((1920, 1080))
        assert len(roi) == 4

    def test_tracker_with_damage_detections(self):
        """Given damage detections, expect tracking considers them."""
        tracker = AdaptiveRoiTracker()
        from PIL import Image

        prev_frame = Image.new("RGB", (1920, 1080), color="black")
        curr_frame = Image.new("RGB", (1920, 1080), color="black")

        detections = [
            {"center_x": 500.0, "center_y": 300.0},
            {"center_x": 600.0, "center_y": 350.0},
        ]

        state = tracker.update(
            curr_frame, prev_frame, frame_index=0,
            damage_detections=detections,
        )

        assert state is not None
        stats = tracker.get_statistics()
        assert stats["damage_positions_tracked"] == 2
