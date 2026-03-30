"""Session-level metrics logging and aggregation.

Aggregates detection statistics across entire sessions.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class SessionMetrics:
    """Aggregated metrics for a detection session.

    Attributes:
        session_id: Session identifier.
        start_time: Session start timestamp.
        end_time: Session end timestamp.
        total_frames: Total frames processed.
        total_candidates: Total candidates examined.
        total_hits: Total hits accepted.
        total_rejected: Total candidates rejected.
        total_damage: Sum of all damage values.
        biggest_hit: Largest single damage value.
        avg_confidence: Average confidence of accepted hits.
        avg_processing_time_ms: Average processing time per frame.
        fps_achieved: Achieved frames per second.
        rejection_reasons: Breakdown of rejection reasons.
        confidence_distribution: Histogram of confidence scores.
        damage_distribution: Histogram of damage values.
    """

    session_id: str
    start_time: str
    end_time: str | None = None
    total_frames: int = 0
    total_candidates: int = 0
    total_hits: int = 0
    total_rejected: int = 0
    total_damage: int = 0
    biggest_hit: int = 0
    avg_confidence: float = 0.0
    avg_processing_time_ms: float = 0.0
    fps_achieved: float = 0.0
    rejection_reasons: dict[str, int] = field(default_factory=dict)
    confidence_distribution: dict[str, int] = field(default_factory=dict)
    damage_distribution: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "total_frames": self.total_frames,
            "total_candidates": self.total_candidates,
            "total_hits": self.total_hits,
            "total_rejected": self.total_rejected,
            "total_damage": self.total_damage,
            "biggest_hit": self.biggest_hit,
            "avg_confidence": round(self.avg_confidence, 4),
            "avg_processing_time_ms": round(self.avg_processing_time_ms, 2),
            "fps_achieved": round(self.fps_achieved, 2),
            "rejection_reasons": self.rejection_reasons,
            "confidence_distribution": self.confidence_distribution,
            "damage_distribution": self.damage_distribution,
            "metadata": self.metadata,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @property
    def acceptance_rate(self) -> float:
        """Calculate acceptance rate."""
        if self.total_candidates == 0:
            return 0.0
        return self.total_hits / self.total_candidates

    @property
    def duration_seconds(self) -> float | None:
        """Calculate session duration in seconds."""
        if not self.end_time:
            return None
        start = datetime.fromisoformat(self.start_time)
        end = datetime.fromisoformat(self.end_time)
        return (end - start).total_seconds()


class MetricsLogger:
    """Logger for session-level metrics.

    Aggregates detection statistics across entire sessions
    and exports summary reports.

    Example:
        logger = MetricsLogger(session_id="session_001")

        # Log frame metrics
        logger.log_frame(
            frame_index=100,
            candidates=5,
            hits=2,
            rejected=3,
            damage_values=[1234, 5678],
            confidences=[0.85, 0.92],
            processing_time_ms=45.2,
        )

        # Get final metrics
        metrics = logger.get_metrics()
        print(f"Total damage: {metrics.total_damage}")
        print(f"Biggest hit: {metrics.biggest_hit}")

        # Export report
        logger.export_report(Path("reports/session_001.json"))
    """

    def __init__(
        self,
        session_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Initialize metrics logger.

        Args:
            session_id: Session identifier.
            metadata: Optional session metadata.
        """
        self.session_id = session_id
        self.start_time = datetime.now().isoformat()
        self.metadata = metadata or {}

        # Accumulators
        self.total_frames = 0
        self.total_candidates = 0
        self.total_hits = 0
        self.total_rejected = 0
        self.total_damage = 0
        self.biggest_hit = 0

        self.confidence_sum = 0.0
        self.processing_time_sum = 0.0

        self.rejection_reasons: dict[str, int] = {}
        self.confidence_buckets: dict[str, int] = {
            "0.0-0.2": 0,
            "0.2-0.4": 0,
            "0.4-0.6": 0,
            "0.6-0.8": 0,
            "0.8-1.0": 0,
        }
        self.damage_buckets: dict[str, int] = {
            "0-1k": 0,
            "1k-10k": 0,
            "10k-100k": 0,
            "100k-1M": 0,
            "1M+": 0,
        }

        # Timing
        self.start_timestamp = time.time()
        self.frame_timestamps: list[float] = []

    def log_frame(
        self,
        frame_index: int,
        candidates: int,
        hits: int,
        rejected: int,
        damage_values: list[int] | None = None,
        confidences: list[float] | None = None,
        processing_time_ms: float = 0.0,
        rejection_reasons: dict[str, int] | None = None,
    ) -> None:
        """Log metrics for a single frame.

        Args:
            frame_index: Frame number.
            candidates: Number of candidates examined.
            hits: Number of hits accepted.
            rejected: Number of candidates rejected.
            damage_values: List of damage values for accepted hits.
            confidences: List of confidence scores for accepted hits.
            processing_time_ms: Processing time for frame.
            rejection_reasons: Breakdown of rejection reasons.
        """
        self.total_frames += 1
        self.total_candidates += candidates
        self.total_hits += hits
        self.total_rejected += rejected
        self.processing_time_sum += processing_time_ms

        # Track frame timing
        self.frame_timestamps.append(time.time())

        # Process damage values
        if damage_values:
            for value in damage_values:
                self.total_damage += value
                if value > self.biggest_hit:
                    self.biggest_hit = value
                self._bucket_damage(value)

        # Process confidences
        if confidences:
            for conf in confidences:
                self.confidence_sum += conf
                self._bucket_confidence(conf)

        # Aggregate rejection reasons
        if rejection_reasons:
            for reason, count in rejection_reasons.items():
                self.rejection_reasons[reason] = (
                    self.rejection_reasons.get(reason, 0) + count
                )

    def _bucket_confidence(self, confidence: float) -> None:
        """Bucket confidence score into histogram."""
        if confidence < 0.2:
            self.confidence_buckets["0.0-0.2"] += 1
        elif confidence < 0.4:
            self.confidence_buckets["0.2-0.4"] += 1
        elif confidence < 0.6:
            self.confidence_buckets["0.4-0.6"] += 1
        elif confidence < 0.8:
            self.confidence_buckets["0.6-0.8"] += 1
        else:
            self.confidence_buckets["0.8-1.0"] += 1

    def _bucket_damage(self, value: int) -> None:
        """Bucket damage value into histogram."""
        if value < 1000:
            self.damage_buckets["0-1k"] += 1
        elif value < 10000:
            self.damage_buckets["1k-10k"] += 1
        elif value < 100000:
            self.damage_buckets["10k-100k"] += 1
        elif value < 1000000:
            self.damage_buckets["100k-1M"] += 1
        else:
            self.damage_buckets["1M+"] += 1

    def get_metrics(self) -> SessionMetrics:
        """Get aggregated session metrics.

        Returns:
            SessionMetrics object with all aggregated statistics.
        """
        # Calculate averages
        avg_confidence = (
            self.confidence_sum / self.total_hits if self.total_hits > 0 else 0.0
        )
        avg_processing_time = (
            self.processing_time_sum / self.total_frames
            if self.total_frames > 0
            else 0.0
        )

        # Calculate FPS
        elapsed = time.time() - self.start_timestamp
        fps_achieved = self.total_frames / elapsed if elapsed > 0 else 0.0

        metrics = SessionMetrics(
            session_id=self.session_id,
            start_time=self.start_time,
            total_frames=self.total_frames,
            total_candidates=self.total_candidates,
            total_hits=self.total_hits,
            total_rejected=self.total_rejected,
            total_damage=self.total_damage,
            biggest_hit=self.biggest_hit,
            avg_confidence=avg_confidence,
            avg_processing_time_ms=avg_processing_time,
            fps_achieved=fps_achieved,
            rejection_reasons=self.rejection_reasons,
            confidence_distribution=self.confidence_buckets,
            damage_distribution=self.damage_buckets,
            metadata=self.metadata,
        )

        return metrics

    def finalize(self) -> SessionMetrics:
        """Finalize the session and return metrics.

        Returns:
            Final SessionMetrics object.
        """
        metrics = self.get_metrics()
        metrics.end_time = datetime.now().isoformat()
        return metrics

    def print_summary(self) -> None:
        """Print session summary to console."""
        metrics = self.get_metrics()

        print(f"\n{'='*60}")
        print(f"Session Metrics: {self.session_id}")
        print(f"{'='*60}")
        print(f"Total frames: {metrics.total_frames}")
        print(f"Total candidates: {metrics.total_candidates}")
        print(f"Total hits: {metrics.total_hits}")
        print(f"Total rejected: {metrics.total_rejected}")
        print(f"Acceptance rate: {metrics.acceptance_rate:.2%}")
        print(f"\nDamage Statistics:")
        print(f"  Total damage: {metrics.total_damage:,}")
        print(f"  Biggest hit: {metrics.biggest_hit:,}")
        print(f"  Avg confidence: {metrics.avg_confidence:.2%}")
        print(f"\nPerformance:")
        print(f"  Avg processing time: {metrics.avg_processing_time_ms:.1f}ms")
        print(f"  FPS achieved: {metrics.fps_achieved:.1f}")
        print(f"\nRejection Reasons:")
        for reason, count in metrics.rejection_reasons.items():
            print(f"  {reason}: {count}")
        print(f"\nConfidence Distribution:")
        for bucket, count in metrics.confidence_distribution.items():
            print(f"  {bucket}: {count}")
        print(f"\nDamage Distribution:")
        for bucket, count in metrics.damage_distribution.items():
            print(f"  {bucket}: {count}")
        print(f"{'='*60}\n")

    def export_report(self, output_path: Path | str) -> None:
        """Export session report to JSON file.

        Args:
            output_path: Path to output file.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        metrics = self.finalize()
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(metrics.to_json())

    def get_frame_rate_analysis(self) -> dict[str, Any]:
        """Analyze frame rate consistency.

        Returns:
            Dictionary with frame rate statistics.
        """
        if len(self.frame_timestamps) < 2:
            return {"error": "Not enough frames for analysis"}

        # Calculate frame deltas
        deltas = []
        for i in range(1, len(self.frame_timestamps)):
            delta = self.frame_timestamps[i] - self.frame_timestamps[i - 1]
            deltas.append(delta)

        # Statistics
        avg_delta = sum(deltas) / len(deltas)
        min_delta = min(deltas)
        max_delta = max(deltas)

        # Calculate standard deviation
        variance = sum((d - avg_delta) ** 2 for d in deltas) / len(deltas)
        std_dev = variance ** 0.5

        return {
            "total_frames": len(self.frame_timestamps),
            "avg_frame_time_s": round(avg_delta, 6),
            "min_frame_time_s": round(min_delta, 6),
            "max_frame_time_s": round(max_delta, 6),
            "std_dev_s": round(std_dev, 6),
            "avg_fps": round(1 / avg_delta, 2) if avg_delta > 0 else 0,
            "min_fps": round(1 / max_delta, 2) if max_delta > 0 else 0,
            "max_fps": round(1 / min_delta, 2) if min_delta > 0 else 0,
        }


class MetricsLoggerFactory:
    """Factory for creating metrics loggers."""

    @staticmethod
    def create(
        session_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> MetricsLogger:
        """Create a metrics logger.

        Args:
            session_id: Session identifier.
            metadata: Optional session metadata.

        Returns:
            Configured MetricsLogger instance.
        """
        return MetricsLogger(session_id=session_id, metadata=metadata)
