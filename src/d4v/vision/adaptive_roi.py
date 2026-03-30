"""Adaptive ROI tracking for dynamic damage capture region.

Expands and contracts the region of interest based on motion detection
and damage text velocity prediction.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Literal

from PIL import Image


@dataclass(frozen=True)
class MotionRegion:
    """Detected motion region.

    Attributes:
        x: X coordinate of region center.
        y: Y coordinate of region center.
        width: Region width.
        height: Region height.
        motion_score: Amount of motion detected (0-1).
        frame: Frame where motion was detected.
    """

    x: float
    y: float
    width: int
    height: int
    motion_score: float
    frame: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "x": round(self.x, 2),
            "y": round(self.y, 2),
            "width": self.width,
            "height": self.height,
            "motion_score": round(self.motion_score, 4),
            "frame": self.frame,
        }


@dataclass
class AdaptiveRoiState:
    """Current state of adaptive ROI.

    Attributes:
        left: Left boundary.
        top: Top boundary.
        right: Right boundary.
        bottom: Bottom boundary.
        expansion_reason: Why ROI was expanded.
        confidence: Confidence in current ROI.
        frames_at_current_size: Frames at current size.
    """

    left: int
    top: int
    right: int
    bottom: int
    expansion_reason: str = ""
    confidence: float = 1.0
    frames_at_current_size: int = 0

    @property
    def width(self) -> int:
        """Get ROI width."""
        return self.right - self.left

    @property
    def height(self) -> int:
        """Get ROI height."""
        return self.bottom - self.top

    def to_tuple(self) -> tuple[int, int, int, int]:
        """Convert to (left, top, right, bottom) tuple."""
        return (self.left, self.top, self.right, self.bottom)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "left": self.left,
            "top": self.top,
            "right": self.right,
            "bottom": self.bottom,
            "width": self.width,
            "height": self.height,
            "expansion_reason": self.expansion_reason,
            "confidence": round(self.confidence, 4),
            "frames_at_current_size": self.frames_at_current_size,
        }


class MotionDetector:
    """Detects motion between frames.

    Example:
        detector = MotionDetector(
            threshold=100,
            min_region_size=500,
        )

        motion_regions = detector.detect_motion(frame1, frame2)
    """

    def __init__(
        self,
        threshold: int = 100,
        min_region_size: int = 500,
        blur_kernel: int = 5,
    ) -> None:
        """Initialize motion detector.

        Args:
            threshold: Motion detection threshold (higher = less sensitive).
            min_region_size: Minimum region size to consider.
            blur_kernel: Gaussian blur kernel size.
        """
        self.threshold = threshold
        self.min_region_size = min_region_size
        self.blur_kernel = blur_kernel

    def detect_motion(
        self,
        current: Image.Image,
        previous: Image.Image | None,
        frame: int = 0,
    ) -> list[MotionRegion]:
        """Detect motion between frames.

        Args:
            current: Current frame.
            previous: Previous frame (None for first frame).
            frame: Current frame index.

        Returns:
            List of motion regions.
        """
        if previous is None:
            return []

        try:
            import cv2
            import numpy as np
        except ImportError:
            return []

        # Convert to grayscale
        curr_gray = cv2.cvtColor(np.array(current.convert("L")), cv2.COLOR_GRAY2BGR)
        prev_gray = cv2.cvtColor(np.array(previous.convert("L")), cv2.COLOR_GRAY2BGR)

        # Apply Gaussian blur
        curr_blur = cv2.GaussianBlur(curr_gray, (self.blur_kernel, self.blur_kernel), 0)
        prev_blur = cv2.GaussianBlur(prev_gray, (self.blur_kernel, self.blur_kernel), 0)

        # Calculate frame difference
        diff = cv2.absdiff(curr_blur, prev_blur)

        # Threshold
        _, thresh = cv2.threshold(diff, self.threshold, 255, cv2.THRESH_BINARY)

        # Dilate to fill gaps
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        dilated = cv2.dilate(thresh, kernel, iterations=2)

        # Find contours
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Extract motion regions
        regions: list[MotionRegion] = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < self.min_region_size:
                continue

            x, y, w, h = cv2.boundingRect(contour)
            motion_score = min(area / 10000, 1.0)  # Normalize

            regions.append(MotionRegion(
                x=x + w / 2,
                y=y + h / 2,
                width=w,
                height=h,
                motion_score=motion_score,
                frame=frame,
            ))

        return regions

    def detect_motion_simple(
        self,
        current: Image.Image,
        previous: Image.Image | None,
    ) -> float:
        """Get simple motion score (0-1).

        Args:
            current: Current frame.
            previous: Previous frame.

        Returns:
            Motion score (0 = no motion, 1 = high motion).
        """
        if previous is None:
            return 0.0

        try:
            import numpy as np
        except ImportError:
            return 0.0

        # Convert to numpy
        curr_arr = np.array(current.convert("L")).astype(float)
        prev_arr = np.array(previous.convert("L")).astype(float)

        # Calculate difference
        diff = np.abs(curr_arr - prev_arr)

        # Calculate motion score
        motion_pixels = np.sum(diff > self.threshold)
        total_pixels = curr_arr.size

        return min(motion_pixels / total_pixels * 10, 1.0)


class AdaptiveRoiTracker:
    """Adaptive ROI tracker with motion-based expansion.

    Example:
        tracker = AdaptiveRoiTracker(
            base_roi=(0.15, 0.05, 0.70, 0.75),
            expansion_margin=100,
            cooldown_frames=30,
        )

        # Update with each frame
        roi = tracker.update(current_frame, previous_frame, frame_index)

        # Get current ROI as tuple
        left, top, right, bottom = tracker.get_roi_tuple(image.size)
    """

    def __init__(
        self,
        base_roi: tuple[float, float, float, float] = (0.15, 0.05, 0.70, 0.75),
        expansion_margin: int = 100,
        cooldown_frames: int = 30,
        motion_threshold: float = 0.1,
        max_expansion: int = 300,
        min_confidence_threshold: float = 0.3,
    ) -> None:
        """Initialize adaptive ROI tracker.

        Args:
            base_roi: Base ROI as (left, top, width, height) fractions.
            expansion_margin: Pixels to expand when motion detected.
            cooldown_frames: Frames before contracting after expansion.
            motion_threshold: Motion score threshold for expansion.
            max_expansion: Maximum expansion in pixels.
            min_confidence_threshold: Minimum confidence to maintain expansion.
        """
        self.base_roi = base_roi
        self.expansion_margin = expansion_margin
        self.cooldown_frames = cooldown_frames
        self.motion_threshold = motion_threshold
        self.max_expansion = max_expansion
        self.min_confidence_threshold = min_confidence_threshold

        self.motion_detector = MotionDetector()
        self.motion_history: deque[float] = deque(maxlen=30)
        self.expansion_cooldown = 0
        self.current_expansion = 0

        # Damage position tracking
        self.damage_positions: deque[tuple[float, float]] = deque(maxlen=60)

    def update(
        self,
        current: Image.Image,
        previous: Image.Image | None,
        frame_index: int,
        damage_detections: list[dict[str, Any]] | None = None,
    ) -> AdaptiveRoiState:
        """Update ROI based on motion and detections.

        Args:
            current: Current frame.
            previous: Previous frame.
            frame_index: Current frame index.
            damage_detections: Optional list of damage detections.

        Returns:
            Current AdaptiveRoiState.
        """
        # Detect motion
        motion_regions = self.motion_detector.detect_motion(current, previous, frame_index)
        motion_score = sum(r.motion_score for r in motion_regions) / max(len(motion_regions), 1)
        self.motion_history.append(motion_score)

        # Track damage positions
        if damage_detections:
            for det in damage_detections:
                self.damage_positions.append((det.get("center_x", 0), det.get("center_y", 0)))

        # Calculate expansion
        expansion = self._calculate_expansion(motion_regions, damage_detections)

        # Update cooldown
        if expansion > 0:
            self.expansion_cooldown = self.cooldown_frames
        else:
            self.expansion_cooldown = max(0, self.expansion_cooldown - 1)

        self.current_expansion = expansion

        # Create state
        state = self._create_state(expansion)

        return state

    def _calculate_expansion(
        self,
        motion_regions: list[MotionRegion],
        damage_detections: list[dict[str, Any]] | None,
    ) -> int:
        """Calculate expansion amount.

        Args:
            motion_regions: Detected motion regions.
            damage_detections: Damage detections.

        Returns:
            Expansion in pixels.
        """
        expansion = 0

        # Check for motion outside base ROI
        for region in motion_regions:
            if region.motion_score > self.motion_threshold:
                # Check if outside base ROI
                if self._is_outside_base_roi(region.x, region.y):
                    expansion = max(expansion, self.expansion_margin)

        # Check for damage near edges
        if damage_detections:
            for det in damage_detections:
                x = det.get("center_x", 0)
                y = det.get("center_y", 0)
                if self._is_near_edge(x, y):
                    expansion = max(expansion, self.expansion_margin // 2)

        # Limit expansion
        expansion = min(expansion, self.max_expansion)

        return expansion

    def _is_outside_base_roi(self, x: float, y: float) -> bool:
        """Check if position is outside base ROI.

        Args:
            x: X coordinate.
            y: Y coordinate.

        Returns:
            True if outside base ROI.
        """
        # This will be called with image size context
        # For now, use simple heuristic
        return False

    def _is_near_edge(self, x: float, y: float) -> bool:
        """Check if position is near ROI edge.

        Args:
            x: X coordinate.
            y: Y coordinate.

        Returns:
            True if near edge.
        """
        return False

    def _create_state(self, expansion: int) -> AdaptiveRoiState:
        """Create ROI state.

        Args:
            expansion: Current expansion in pixels.

        Returns:
            AdaptiveRoiState.
        """
        # Base ROI
        left = int(1920 * self.base_roi[0]) - expansion
        top = int(1080 * self.base_roi[1]) - expansion
        right = int(1920 * (self.base_roi[0] + self.base_roi[2])) + expansion
        bottom = int(1080 * (self.base_roi[1] + self.base_roi[3])) + expansion

        # Clamp to valid range
        left = max(0, left)
        top = max(0, top)

        # Determine expansion reason
        reason = ""
        if expansion > 0:
            if self.expansion_cooldown == self.cooldown_frames:
                reason = "motion_detected"
            else:
                reason = "cooldown"

        # Calculate confidence
        confidence = 1.0 - (expansion / self.max_expansion) if self.max_expansion > 0 else 1.0

        return AdaptiveRoiState(
            left=left,
            top=top,
            right=right,
            bottom=bottom,
            expansion_reason=reason,
            confidence=confidence,
            frames_at_current_size=self.expansion_cooldown,
        )

    def get_roi_tuple(
        self,
        image_size: tuple[int, int],
    ) -> tuple[int, int, int, int]:
        """Get ROI as (left, top, right, bottom) tuple.

        Args:
            image_size: Image (width, height).

        Returns:
            ROI tuple.
        """
        width, height = image_size

        left = int(width * self.base_roi[0]) - self.current_expansion
        top = int(height * self.base_roi[1]) - self.current_expansion
        right = int(width * (self.base_roi[0] + self.base_roi[2])) + self.current_expansion
        bottom = int(height * (self.base_roi[1] + self.base_roi[3])) + self.current_expansion

        # Clamp
        left = max(0, left)
        top = max(0, top)
        right = min(width, right)
        bottom = min(height, bottom)

        return (left, top, right, bottom)

    def get_predicted_roi(
        self,
        image_size: tuple[int, int],
        frames_ahead: int = 5,
    ) -> tuple[int, int, int, int]:
        """Get predicted ROI for future frame.

        Args:
            image_size: Image (width, height).
            frames_ahead: Frames to predict ahead.

        Returns:
            Predicted ROI tuple.
        """
        # Use current ROI with potential expansion based on motion trend
        if len(self.motion_history) >= 5:
            recent_motion = sum(list(self.motion_history)[-5:]) / 5
            if recent_motion > self.motion_threshold * 1.5:
                # Increasing motion - expand prediction
                predicted_expansion = min(
                    self.current_expansion + self.expansion_margin,
                    self.max_expansion,
                )
            else:
                predicted_expansion = self.current_expansion
        else:
            predicted_expansion = self.current_expansion

        width, height = image_size

        left = int(width * self.base_roi[0]) - predicted_expansion
        top = int(height * self.base_roi[1]) - predicted_expansion
        right = int(width * (self.base_roi[0] + self.base_roi[2])) + predicted_expansion
        bottom = int(height * (self.base_roi[1] + self.base_roi[3])) + predicted_expansion

        # Clamp
        left = max(0, left)
        top = max(0, top)
        right = min(width, right)
        bottom = min(height, bottom)

        return (left, top, right, bottom)

    def reset(self) -> None:
        """Reset tracker state."""
        self.motion_history.clear()
        self.damage_positions.clear()
        self.expansion_cooldown = 0
        self.current_expansion = 0

    def get_statistics(self) -> dict[str, Any]:
        """Get tracker statistics.

        Returns:
            Dictionary of statistics.
        """
        avg_motion = sum(self.motion_history) / len(self.motion_history) if self.motion_history else 0.0

        return {
            "current_expansion": self.current_expansion,
            "expansion_cooldown": self.expansion_cooldown,
            "avg_motion_score": round(avg_motion, 4),
            "damage_positions_tracked": len(self.damage_positions),
        }


class RoiPredictor:
    """Predicts optimal ROI based on damage text patterns.

    Uses historical damage positions to predict where future
    damage will appear.
    """

    def __init__(
        self,
        history_size: int = 100,
        prediction_frames: int = 10,
    ) -> None:
        """Initialize ROI predictor.

        Args:
            history_size: Number of frames to track.
            prediction_frames: Frames to predict ahead.
        """
        self.history_size = history_size
        self.prediction_frames = prediction_frames
        self.position_history: deque[tuple[int, float, float]] = deque(maxlen=history_size)

    def add_position(self, frame: int, x: float, y: float) -> None:
        """Add damage position to history.

        Args:
            frame: Frame index.
            x: X coordinate.
            y: Y coordinate.
        """
        self.position_history.append((frame, x, y))

    def predict_spawn_region(
        self,
        image_size: tuple[int, int],
    ) -> tuple[int, int, int, int]:
        """Predict where damage will spawn.

        Args:
            image_size: Image (width, height).

        Returns:
            Predicted spawn region (left, top, right, bottom).
        """
        if len(self.position_history) < 10:
            # Not enough data - use default
            width, height = image_size
            return (
                int(width * 0.15),
                int(height * 0.05),
                int(width * 0.85),
                int(height * 0.5),
            )

        # Analyze spawn positions (where damage first appears)
        spawn_positions = self._extract_spawn_positions()

        if not spawn_positions:
            width, height = image_size
            return (
                int(width * 0.15),
                int(height * 0.05),
                int(width * 0.85),
                int(height * 0.5),
            )

        # Calculate bounding box of spawn positions
        xs = [p[1] for p in spawn_positions]
        ys = [p[2] for p in spawn_positions]

        margin = 50
        return (
            max(0, min(xs) - margin),
            max(0, min(ys) - margin),
            min(image_size[0], max(xs) + margin),
            min(image_size[1], max(ys) + margin),
        )

    def _extract_spawn_positions(self) -> list[tuple[int, float, float]]:
        """Extract positions where damage first spawns.

        Returns:
            List of (frame, x, y) tuples.
        """
        spawns: list[tuple[int, float, float]] = []
        prev_y = None

        for frame, x, y in self.position_history:
            # Damage spawns at bottom of its trajectory
            # Look for positions where y starts decreasing (moving up)
            if prev_y is not None and y < prev_y:
                # Check if this is a new spawn (not continuation)
                if not spawns or frame - spawns[-1][0] > 5:
                    spawns.append((frame, x, y))
            prev_y = y

        return spawns

    def get_velocity_estimate(self) -> tuple[float, float]:
        """Estimate average damage text velocity.

        Returns:
            Tuple of (velocity_x, velocity_y) pixels per frame.
        """
        if len(self.position_history) < 5:
            return (0.0, -2.0)  # Default upward velocity

        velocities_x: list[float] = []
        velocities_y: list[float] = []

        history = list(self.position_history)
        for i in range(1, len(history)):
            prev_frame, prev_x, prev_y = history[i - 1]
            curr_frame, curr_x, curr_y = history[i]

            frame_diff = max(curr_frame - prev_frame, 1)
            velocities_x.append((curr_x - prev_x) / frame_diff)
            velocities_y.append((curr_y - prev_y) / frame_diff)

        avg_vx = sum(velocities_x) / len(velocities_x)
        avg_vy = sum(velocities_y) / len(velocities_y)

        return (avg_vx, avg_vy)
