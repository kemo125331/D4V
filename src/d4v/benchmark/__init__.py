"""Benchmarking infrastructure for D4V detection evaluation.

This package provides tools for:
- Annotating replay frames with ground truth damage hits
- Computing precision, recall, F1 score metrics
- Running benchmark suites on annotated replays
- Comparing benchmark results (before/after changes)

Example:
    from d4v.benchmark import (
        BenchmarkAnnotation,
        AnnotationBuilder,
        BenchmarkMetrics,
    )

    # Create annotation
    annotation = (
        AnnotationBuilder(session_id="session_001")
        .with_metadata(
            session_name="Test Combat",
            resolution="1920x1080",
            ui_scale=100.0,
            total_frames=1000,
            fps=30.0,
        )
        .add_hit(frame=10, value=1234, x=500, y=300)
        .build()
    )

    # Run benchmark (requires cv2)
    # from d4v.benchmark.runner import BenchmarkRunner
    # runner = BenchmarkRunner()
    # result = runner.run_benchmark(annotation)
"""

from d4v.benchmark.annotation import (
    AnnotationBuilder,
    BenchmarkAnnotation,
    GroundTruthHit,
    load_benchmark_annotations,
    save_benchmark_annotations,
)
from d4v.benchmark.metrics import (
    BenchmarkMetrics,
    compute_metrics,
    compute_per_frame_metrics,
    compute_value_range_metrics,
    match_detections_to_ground_truth,
)

__all__ = [
    # Annotation
    "AnnotationBuilder",
    "BenchmarkAnnotation",
    "GroundTruthHit",
    "load_benchmark_annotations",
    "save_benchmark_annotations",
    # Metrics
    "BenchmarkMetrics",
    "compute_metrics",
    "compute_per_frame_metrics",
    "compute_value_range_metrics",
    "match_detections_to_ground_truth",
    # Runner (import separately to avoid cv2 dependency for metrics-only usage)
    # from d4v.benchmark.runner import BenchmarkConfig, BenchmarkResult, BenchmarkRunner
]
