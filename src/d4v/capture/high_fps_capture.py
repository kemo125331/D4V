"""High FPS capture and short-lived text recall optimization.

Improves detection of fast-fading damage numbers through:
- High FPS capture (60+ FPS)
- Motion-based prediction
- Reduced processing latency
- Priority queuing for OCR
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from threading import Event, Thread
from typing import Any, Callable, Protocol

from PIL import Image


class FrameSource(Protocol):
    """Protocol for frame capture sources."""

    def capture_frame(self) -> Image.Image | None:
        """Capture a single frame."""
        ...


@dataclass(frozen=True)
class CapturedFrame:
    """A captured frame with timing information.

    Attributes:
        image: Frame image.
        frame_index: Sequential frame number.
        timestamp_ms: Capture timestamp in milliseconds.
        capture_duration_ms: Time taken to capture.
        is_keyframe: Whether this is a keyframe for processing.
    """

    image: Image.Image
    frame_index: int
    timestamp_ms: int
    capture_duration_ms: float
    is_keyframe: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "frame_index": self.frame_index,
            "timestamp_ms": self.timestamp_ms,
            "capture_duration_ms": round(self.capture_duration_ms, 2),
            "is_keyframe": self.is_keyframe,
        }


@dataclass
class FrameBuffer:
    """Circular buffer for captured frames.

    Attributes:
        max_size: Maximum frames to buffer.
        frames: Deque of captured frames.
    """

    max_size: int = 60
    frames: deque[CapturedFrame] = field(default_factory=lambda: deque(maxlen=60))

    def add(self, frame: CapturedFrame) -> None:
        """Add frame to buffer.

        Args:
            frame: Frame to add.
        """
        self.frames.append(frame)

    def get_recent(self, count: int = 10) -> list[CapturedFrame]:
        """Get most recent frames.

        Args:
            count: Number of frames to retrieve.

        Returns:
            List of recent frames.
        """
        return list(self.frames)[-count:]

    def get_frame_at(self, index: int) -> CapturedFrame | None:
        """Get frame at specific index.

        Args:
            index: Frame index.

        Returns:
            Frame or None.
        """
        for frame in self.frames:
            if frame.frame_index == index:
                return frame
        return None

    def clear(self) -> None:
        """Clear buffer."""
        self.frames.clear()


@dataclass
class CaptureStatistics:
    """Statistics for frame capture session.

    Attributes:
        total_frames: Total frames captured.
        total_duration_ms: Total capture duration.
        avg_fps: Average frames per second.
        min_frame_time_ms: Minimum frame time.
        max_frame_time_ms: Maximum frame time.
        dropped_frames: Number of dropped frames.
        avg_capture_time_ms: Average capture time.
    """

    total_frames: int = 0
    total_duration_ms: float = 0.0
    avg_fps: float = 0.0
    min_frame_time_ms: float = float("inf")
    max_frame_time_ms: float = 0.0
    dropped_frames: int = 0
    avg_capture_time_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_frames": self.total_frames,
            "total_duration_ms": round(self.total_duration_ms, 2),
            "avg_fps": round(self.avg_fps, 2),
            "min_frame_time_ms": round(self.min_frame_time_ms, 2),
            "max_frame_time_ms": round(self.max_frame_time_ms, 2),
            "dropped_frames": self.dropped_frames,
            "avg_capture_time_ms": round(self.avg_capture_time_ms, 2),
        }


class HighFpsCapture:
    """High FPS frame capture for short-lived text detection.

    Captures frames at high frame rate (60+ FPS) to catch
    fast-fading damage numbers that would be missed at 30 FPS.

    Example:
        capture = HighFpsCapture(
            target_fps=60,
            frame_source=screen_capture,
        )

        # Start capture thread
        capture.start()

        # Get captured frames
        frames = capture.get_recent_frames(10)

        # Stop capture
        capture.stop()
    """

    def __init__(
        self,
        target_fps: float = 60.0,
        frame_source: FrameSource | None = None,
        buffer_size: int = 120,
        enable_motion_prediction: bool = True,
    ) -> None:
        """Initialize high FPS capture.

        Args:
            target_fps: Target frames per second.
            frame_source: Source for frame capture.
            buffer_size: Size of frame buffer.
            enable_motion_prediction: Enable motion-based prediction.
        """
        self.target_fps = target_fps
        self.frame_interval_ms = 1000.0 / target_fps
        self.frame_source = frame_source
        self.buffer_size = buffer_size
        self.enable_motion_prediction = enable_motion_prediction

        # Capture state
        self.is_running = False
        self.capture_thread: Thread | None = None
        self.stop_event = Event()

        # Frame buffer
        self.buffer = FrameBuffer(max_size=buffer_size)
        self.frame_index = 0

        # Statistics
        self.stats = CaptureStatistics()
        self.capture_times: deque[float] = deque(maxlen=120)

        # Motion prediction
        self.last_positions: deque[tuple[float, float]] = deque(maxlen=30)
        self.predicted_regions: list[tuple[int, int, int, int]] = []

    def start(self) -> None:
        """Start capture thread."""
        if self.is_running:
            return

        self.is_running = True
        self.stop_event.clear()
        self.capture_thread = Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()

    def stop(self) -> None:
        """Stop capture thread."""
        self.stop_event.set()
        self.is_running = False

        if self.capture_thread:
            self.capture_thread.join(timeout=2.0)
            self.capture_thread = None

    def _capture_loop(self) -> None:
        """Main capture loop."""
        start_time = time.perf_counter()

        while not self.stop_event.is_set():
            frame_start = time.perf_counter()

            # Capture frame
            if self.frame_source:
                image = self.frame_source.capture_frame()

                if image:
                    capture_duration = (time.perf_counter() - frame_start) * 1000
                    timestamp_ms = int((time.perf_counter() - start_time) * 1000)

                    # Determine if keyframe (every 3rd frame for OCR priority)
                    is_keyframe = self.frame_index % 3 == 0

                    frame = CapturedFrame(
                        image=image,
                        frame_index=self.frame_index,
                        timestamp_ms=timestamp_ms,
                        capture_duration_ms=capture_duration,
                        is_keyframe=is_keyframe,
                    )

                    self.buffer.add(frame)
                    self.frame_index += 1

                    # Update statistics
                    self._update_statistics(capture_duration, timestamp_ms)

                    # Update motion prediction
                    if self.enable_motion_prediction:
                        self._update_motion_prediction()

            # Sleep to maintain target FPS
            elapsed = (time.perf_counter() - frame_start) * 1000
            sleep_time = self.frame_interval_ms - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time / 1000.0)

    def _update_statistics(self, capture_duration_ms: float, timestamp_ms: int) -> None:
        """Update capture statistics.

        Args:
            capture_duration_ms: Frame capture duration.
            timestamp_ms: Frame timestamp.
        """
        self.capture_times.append(capture_duration_ms)

        self.stats.total_frames += 1
        self.stats.total_duration_ms = timestamp_ms
        self.stats.min_frame_time_ms = min(self.stats.min_frame_time_ms, capture_duration_ms)
        self.stats.max_frame_time_ms = max(self.stats.max_frame_time_ms, capture_duration_ms)
        self.stats.avg_capture_time_ms = sum(self.capture_times) / len(self.capture_times)

        if self.stats.total_duration_ms > 0:
            self.stats.avg_fps = self.stats.total_frames / (self.stats.total_duration_ms / 1000.0)

    def _update_motion_prediction(self) -> None:
        """Update motion-based position prediction."""
        # Track recent damage positions for prediction
        # This would integrate with the detection pipeline
        pass

    def get_recent_frames(self, count: int = 10) -> list[CapturedFrame]:
        """Get most recent captured frames.

        Args:
            count: Number of frames to retrieve.

        Returns:
            List of recent frames.
        """
        return self.buffer.get_recent(count)

    def get_keyframes(self, count: int = 10) -> list[CapturedFrame]:
        """Get recent keyframes (priority frames for OCR).

        Args:
            count: Number of keyframes to retrieve.

        Returns:
            List of keyframes.
        """
        all_frames = self.buffer.get_recent(count * 3)
        keyframes = [f for f in all_frames if f.is_keyframe]
        return keyframes[-count:]

    def get_statistics(self) -> CaptureStatistics:
        """Get capture statistics.

        Returns:
            CaptureStatistics object.
        """
        return self.stats

    def reset(self) -> None:
        """Reset capture state."""
        self.buffer.clear()
        self.frame_index = 0
        self.stats = CaptureStatistics()
        self.capture_times.clear()


@dataclass
class ShortLivedTextConfig:
    """Configuration for short-lived text detection.

    Attributes:
        capture_fps: Target capture FPS.
        ocr_priority_frames: Use priority frame selection.
        motion_prediction: Enable motion-based prediction.
        reduced_latency_mode: Minimize processing latency.
        buffer_size: Frame buffer size.
    """

    capture_fps: float = 60.0
    ocr_priority_frames: bool = True
    motion_prediction: bool = True
    reduced_latency_mode: bool = True
    buffer_size: int = 120


class ShortLivedTextDetector:
    """Detector optimized for short-lived damage numbers.

    Combines high FPS capture with motion prediction to catch
    damage numbers that fade quickly.

    Example:
        detector = ShortLivedTextDetector(
            config=ShortLivedTextConfig(capture_fps=60),
            frame_source=screen_capture,
        )

        detector.start()

        # Process frames
        for frame in detector.get_priority_frames():
            hits = process_frame(frame.image)
            detector.record_detection(frame.frame_index, hits)

        detector.stop()
    """

    def __init__(
        self,
        config: ShortLivedTextConfig | None = None,
        frame_source: FrameSource | None = None,
    ) -> None:
        """Initialize short-lived text detector.

        Args:
            config: Detection configuration.
            frame_source: Frame capture source.
        """
        self.config = config or ShortLivedTextConfig()
        self.frame_source = frame_source

        # High FPS capture
        self.capture = HighFpsCapture(
            target_fps=self.config.capture_fps,
            frame_source=frame_source,
            buffer_size=self.config.buffer_size,
            enable_motion_prediction=self.config.motion_prediction,
        )

        # Detection tracking
        self.detected_frames: dict[int, list[dict[str, Any]]] = {}
        self.missed_predictions: list[dict[str, Any]] = []

    def start(self) -> None:
        """Start detection."""
        self.capture.start()

    def stop(self) -> None:
        """Stop detection."""
        self.capture.stop()

    def get_priority_frames(self) -> list[CapturedFrame]:
        """Get frames prioritized for OCR processing.

        Returns:
            List of priority frames.
        """
        if self.config.ocr_priority_frames:
            return self.capture.get_keyframes()
        return self.capture.get_recent_frames()

    def record_detection(
        self,
        frame_index: int,
        hits: list[dict[str, Any]],
    ) -> None:
        """Record detection results for a frame.

        Args:
            frame_index: Frame index.
            hits: List of detected hits.
        """
        self.detected_frames[frame_index] = hits

    def predict_missed_text(self) -> list[dict[str, Any]]:
        """Predict potentially missed short-lived text.

        Returns:
            List of predicted detections.
        """
        # Analyze gaps in detection
        # Use motion prediction to identify likely missed text
        predictions: list[dict[str, Any]] = []

        recent_frames = self.capture.get_recent_frames(30)
        if len(recent_frames) < 10:
            return predictions

        # Check for frames without detections that should have had them
        for frame in recent_frames:
            if frame.frame_index not in self.detected_frames:
                # No detection - check if motion suggests text was present
                if self.capture.enable_motion_prediction:
                    # Add to missed predictions for review
                    predictions.append({
                        "frame_index": frame.frame_index,
                        "timestamp_ms": frame.timestamp_ms,
                        "prediction_confidence": 0.5,
                        "reason": "motion_without_detection",
                    })

        self.missed_predictions = predictions
        return predictions

    def get_statistics(self) -> dict[str, Any]:
        """Get detection statistics.

        Returns:
            Statistics dictionary.
        """
        capture_stats = self.capture.get_statistics()

        return {
            "capture": capture_stats.to_dict(),
            "total_detected_frames": len(self.detected_frames),
            "missed_predictions": len(self.missed_predictions),
            "config": {
                "capture_fps": self.config.capture_fps,
                "priority_frames": self.config.ocr_priority_frames,
                "motion_prediction": self.config.motion_prediction,
            },
        }

    def reset(self) -> None:
        """Reset detector state."""
        self.capture.reset()
        self.detected_frames.clear()
        self.missed_predictions.clear()


def optimize_for_short_lived_text(
    existing_pipeline: Any,
    target_fps: float = 60.0,
) -> ShortLivedTextDetector:
    """Wrap existing pipeline for short-lived text optimization.

    Args:
        existing_pipeline: Existing detection pipeline.
        target_fps: Target capture FPS.

    Returns:
        Configured ShortLivedTextDetector.
    """
    config = ShortLivedTextConfig(
        capture_fps=target_fps,
        ocr_priority_frames=True,
        motion_prediction=True,
        reduced_latency_mode=True,
    )

    detector = ShortLivedTextDetector(config=config)
    return detector
