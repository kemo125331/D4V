"""Benchmark runner for executing detection pipeline on annotated replays.

Compares detection results against ground truth annotations and computes metrics.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image

from d4v.benchmark.annotation import (
    BenchmarkAnnotation,
    GroundTruthHit,
    load_benchmark_annotations,
)
from d4v.benchmark.metrics import BenchmarkMetrics, compute_metrics, compute_per_frame_metrics
from d4v.vision.pipeline import CombatTextPipeline, DetectedHit
from d4v.vision.config import VisionConfig


@dataclass
class BenchmarkResult:
    """Results from running a benchmark.

    Attributes:
        session_id: Session identifier.
        session_name: Human-readable session name.
        total_frames: Total frames processed.
        total_ground_truth_hits: Total hits in ground truth.
        total_detected_hits: Total hits detected.
        metrics: Overall benchmark metrics (precision, recall, F1).
        per_frame_metrics: Metrics broken down by frame.
        processing_time_seconds: Total processing time.
        fps_processed: Frames per second achieved.
        config_used: Vision configuration used for the run.
        errors: Any errors encountered during processing.
    """

    session_id: str
    session_name: str
    total_frames: int
    total_ground_truth_hits: int
    total_detected_hits: int
    metrics: BenchmarkMetrics
    per_frame_metrics: dict[int, BenchmarkMetrics] = field(default_factory=dict)
    processing_time_seconds: float = 0.0
    fps_processed: float = 0.0
    config_used: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "session_id": self.session_id,
            "session_name": self.session_name,
            "total_frames": self.total_frames,
            "total_ground_truth_hits": self.total_ground_truth_hits,
            "total_detected_hits": self.total_detected_hits,
            "metrics": self.metrics.to_dict(),
            "per_frame_metrics": {
                str(frame): m.to_dict()
                for frame, m in self.per_frame_metrics.items()
            },
            "processing_time_seconds": round(self.processing_time_seconds, 3),
            "fps_processed": round(self.fps_processed, 2),
            "config_used": self.config_used,
            "errors": self.errors,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def to_file(self, path: Path | str) -> None:
        """Save results to JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())

    @classmethod
    def from_file(cls, path: Path | str) -> BenchmarkResult:
        """Load results from JSON file."""
        path = Path(path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.loads(f.read())

        metrics = BenchmarkMetrics(
            true_positives=data["metrics"]["true_positives"],
            false_positives=data["metrics"]["false_positives"],
            false_negatives=data["metrics"]["false_negatives"],
            true_negatives=data["metrics"].get("true_negatives", 0),
        )

        per_frame = {}
        for frame_str, m_data in data.get("per_frame_metrics", {}).items():
            per_frame[int(frame_str)] = BenchmarkMetrics(
                true_positives=m_data["true_positives"],
                false_positives=m_data["false_positives"],
                false_negatives=m_data["false_negatives"],
                true_negatives=m_data.get("true_negatives", 0),
            )

        return cls(
            session_id=data["session_id"],
            session_name=data["session_name"],
            total_frames=data["total_frames"],
            total_ground_truth_hits=data["total_ground_truth_hits"],
            total_detected_hits=data["total_detected_hits"],
            metrics=metrics,
            per_frame_metrics=per_frame,
            processing_time_seconds=data["processing_time_seconds"],
            fps_processed=data["fps_processed"],
            config_used=data.get("config_used", {}),
            errors=data.get("errors", []),
        )


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark execution.

    Attributes:
        frame_tolerance: Frame difference tolerance for matching.
        value_tolerance: Value difference tolerance (as fraction, 0.1 = 10%).
        spatial_tolerance: Spatial distance tolerance in pixels.
        compute_per_frame: Whether to compute per-frame metrics.
        replay_frames_dir: Directory containing replay frame PNGs.
    """

    frame_tolerance: int = 3
    value_tolerance: float = 0.1
    spatial_tolerance: float = 70.0
    compute_per_frame: bool = True
    replay_frames_dir: Path | None = None


class BenchmarkRunner:
    """Executes detection pipeline on annotated replays and computes metrics.

    Example:
        runner = BenchmarkRunner()
        result = runner.run_benchmark(
            annotation=annotation,
            config=BenchmarkConfig(replay_frames_dir=Path("fixtures/replays/session_001/frames")),
        )
        print(f"Precision: {result.metrics.precision:.2%}")
        print(f"Recall: {result.metrics.recall:.2%}")
        print(f"F1 Score: {result.metrics.f1_score:.2%}")
    """

    def __init__(self, vision_config: VisionConfig | None = None) -> None:
        """Initialize benchmark runner.

        Args:
            vision_config: Vision configuration for the pipeline.
        """
        self.vision_config = vision_config or VisionConfig()
        self.pipeline = CombatTextPipeline(config=self.vision_config)

    def run_benchmark(
        self,
        annotation: BenchmarkAnnotation,
        config: BenchmarkConfig | None = None,
    ) -> BenchmarkResult:
        """Run benchmark on a single annotated session.

        Args:
            annotation: Ground truth annotation for the session.
            config: Benchmark execution configuration.

        Returns:
            BenchmarkResult with metrics and statistics.
        """
        config = config or BenchmarkConfig()
        errors: list[str] = []

        # Load replay frames
        frames_dir = config.replay_frames_dir
        if frames_dir is None:
            frames_dir = Path(__file__).parent.parent.parent.parent / "fixtures" / "replays" / annotation.session_id / "frames"

        frame_paths = sorted(frames_dir.glob("frame_*.png")) if frames_dir.exists() else []

        if len(frame_paths) == 0:
            errors.append(f"No frame images found in {frames_dir}")
            return self._create_empty_result(annotation, errors)

        # Run detection pipeline
        start_time = time.time()
        all_detections: list[dict] = []

        for frame_index, frame_path in enumerate(frame_paths):
            try:
                image = Image.open(frame_path).convert("RGB")
                timestamp_ms = int(frame_index * (1000 / annotation.fps))

                hits = self.pipeline.process_image(
                    image=image,
                    frame_index=frame_index,
                    timestamp_ms=timestamp_ms,
                )

                for hit in hits:
                    all_detections.append({
                        "frame": frame_index,
                        "value": hit.parsed_value,
                        "center_x": hit.center_x,
                        "center_y": hit.center_y,
                        "confidence": hit.confidence,
                    })

            except Exception as e:
                errors.append(f"Error processing frame {frame_index}: {e}")

        processing_time = time.time() - start_time
        fps_processed = len(frame_paths) / processing_time if processing_time > 0 else 0.0

        # Convert ground truth to dict format
        ground_truth_dicts = [
            {
                "frame": hit.frame,
                "value": hit.value,
                "x": hit.x,
                "y": hit.y,
            }
            for hit in annotation.hits
        ]

        # Compute metrics
        metrics = compute_metrics(
            detections=all_detections,
            ground_truth=ground_truth_dicts,
            frame_tolerance=config.frame_tolerance,
            value_tolerance=config.value_tolerance,
            spatial_tolerance=config.spatial_tolerance,
        )

        per_frame_metrics: dict[int, BenchmarkMetrics] = {}
        if config.compute_per_frame:
            per_frame_metrics = compute_per_frame_metrics(
                detections=all_detections,
                ground_truth=ground_truth_dicts,
                frame_tolerance=config.frame_tolerance,
                value_tolerance=config.value_tolerance,
                spatial_tolerance=config.spatial_tolerance,
            )

        return BenchmarkResult(
            session_id=annotation.session_id,
            session_name=annotation.session_name,
            total_frames=len(frame_paths),
            total_ground_truth_hits=len(annotation.hits),
            total_detected_hits=len(all_detections),
            metrics=metrics,
            per_frame_metrics=per_frame_metrics,
            processing_time_seconds=processing_time,
            fps_processed=fps_processed,
            config_used=self.vision_config.__dict__.copy(),
            errors=errors,
        )

    def _create_empty_result(
        self,
        annotation: BenchmarkAnnotation,
        errors: list[str],
    ) -> BenchmarkResult:
        """Create an empty result for failed benchmarks."""
        return BenchmarkResult(
            session_id=annotation.session_id,
            session_name=annotation.session_name,
            total_frames=0,
            total_ground_truth_hits=len(annotation.hits),
            total_detected_hits=0,
            metrics=BenchmarkMetrics(
                true_positives=0,
                false_positives=0,
                false_negatives=len(annotation.hits),
            ),
            processing_time_seconds=0.0,
            fps_processed=0.0,
            config_used=self.vision_config.__dict__.copy(),
            errors=errors,
        )

    def run_all_benchmarks(
        self,
        fixtures_dir: Path | str | None = None,
        config: BenchmarkConfig | None = None,
    ) -> list[BenchmarkResult]:
        """Run benchmarks on all annotated sessions.

        Args:
            fixtures_dir: Directory containing benchmark JSON files.
            config: Benchmark execution configuration.

        Returns:
            List of BenchmarkResult objects.
        """
        annotations = load_benchmark_annotations(fixtures_dir)
        results: list[BenchmarkResult] = []

        for annotation in annotations:
            print(f"Running benchmark: {annotation.session_name}")
            result = self.run_benchmark(annotation, config)
            results.append(result)
            print(f"  Precision: {result.metrics.precision:.2%}")
            print(f"  Recall: {result.metrics.recall:.2%}")
            print(f"  F1 Score: {result.metrics.f1_score:.2%}")

        return results


def compare_benchmark_results(
    before: BenchmarkResult,
    after: BenchmarkResult,
) -> dict[str, Any]:
    """Compare two benchmark results to show improvements or regressions.

    Args:
        before: Baseline benchmark result.
        after: New benchmark result.

    Returns:
        Dictionary with comparison metrics.
    """
    def delta(old: float, new: float) -> float:
        return new - old

    def percent_change(old: float, new: float) -> float:
        if old == 0:
            return float("inf") if new != 0 else 0.0
        return ((new - old) / old) * 100

    return {
        "session_id": before.session_id,
        "precision": {
            "before": before.metrics.precision,
            "after": after.metrics.precision,
            "delta": delta(before.metrics.precision, after.metrics.precision),
            "percent_change": percent_change(before.metrics.precision, after.metrics.precision),
        },
        "recall": {
            "before": before.metrics.recall,
            "after": after.metrics.recall,
            "delta": delta(before.metrics.recall, after.metrics.recall),
            "percent_change": percent_change(before.metrics.recall, after.metrics.recall),
        },
        "f1_score": {
            "before": before.metrics.f1_score,
            "after": after.metrics.f1_score,
            "delta": delta(before.metrics.f1_score, after.metrics.f1_score),
            "percent_change": percent_change(before.metrics.f1_score, after.metrics.f1_score),
        },
        "fps_processed": {
            "before": before.fps_processed,
            "after": after.fps_processed,
            "delta": delta(before.fps_processed, after.fps_processed),
            "percent_change": percent_change(before.fps_processed, after.fps_processed),
        },
    }
