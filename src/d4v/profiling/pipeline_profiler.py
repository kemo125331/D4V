"""Pipeline profiling for performance analysis.

Provides stage-level timing, memory tracking, and bottleneck identification.
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class StageProfile:
    """Profiling results for a single pipeline stage.

    Attributes:
        name: Stage name (e.g., "color_mask", "segmentation", "ocr").
        call_count: Number of times stage was executed.
        total_time_ms: Total time spent in stage.
        min_time_ms: Minimum execution time.
        max_time_ms: Maximum execution time.
        mean_time_ms: Mean execution time.
        p50_time_ms: 50th percentile (median).
        p95_time_ms: 95th percentile.
        p99_time_ms: 99th percentile.
        std_dev_ms: Standard deviation.
    """

    name: str
    call_count: int
    total_time_ms: float
    min_time_ms: float
    max_time_ms: float
    mean_time_ms: float
    p50_time_ms: float
    p95_time_ms: float
    p99_time_ms: float
    std_dev_ms: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "call_count": self.call_count,
            "total_time_ms": round(self.total_time_ms, 3),
            "min_time_ms": round(self.min_time_ms, 3),
            "max_time_ms": round(self.max_time_ms, 3),
            "mean_time_ms": round(self.mean_time_ms, 3),
            "p50_time_ms": round(self.p50_time_ms, 3),
            "p95_time_ms": round(self.p95_time_ms, 3),
            "p99_time_ms": round(self.p99_time_ms, 3),
            "std_dev_ms": round(self.std_dev_ms, 3),
        }

    @property
    def percentage_of_total(self) -> float:
        """Calculate percentage of total pipeline time."""
        return self.total_time_ms / max(self.total_time_ms, 1) * 100


@dataclass
class PipelineProfile:
    """Complete pipeline profiling results.

    Attributes:
        session_id: Session identifier.
        start_time: Profiling start timestamp.
        end_time: Profiling end timestamp.
        total_frames: Total frames processed.
        total_time_seconds: Total profiling duration.
        stages: Stage-level profiling results.
        pipeline_time_ms: Total pipeline time (sum of stages).
        overhead_time_ms: Time not accounted for by stages.
        fps_achieved: Frames per second achieved.
        fps_target: Target FPS (if configured).
        bottlenecks: Identified performance bottlenecks.
        recommendations: Performance optimization recommendations.
    """

    session_id: str
    start_time: str
    end_time: str | None = None
    total_frames: int = 0
    total_time_seconds: float = 0.0
    stages: dict[str, StageProfile] = field(default_factory=dict)
    pipeline_time_ms: float = 0.0
    overhead_time_ms: float = 0.0
    fps_achieved: float = 0.0
    fps_target: float | None = None
    bottlenecks: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "total_frames": self.total_frames,
            "total_time_seconds": round(self.total_time_seconds, 3),
            "stages": {k: v.to_dict() for k, v in self.stages.items()},
            "pipeline_time_ms": round(self.pipeline_time_ms, 3),
            "overhead_time_ms": round(self.overhead_time_ms, 3),
            "fps_achieved": round(self.fps_achieved, 2),
            "fps_target": self.fps_target,
            "bottlenecks": self.bottlenecks,
            "recommendations": self.recommendations,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


class StageTimer:
    """Context manager for timing pipeline stages.

    Example:
        profiler = PipelineProfiler()

        with profiler.time_stage("color_mask"):
            mask = build_combat_text_mask(image)

        with profiler.time_stage("segmentation"):
            components = segment_damage_tokens(mask)
    """

    def __init__(
        self,
        profiler: PipelineProfiler,
        stage_name: str,
    ) -> None:
        """Initialize stage timer.

        Args:
            profiler: Parent profiler instance.
            stage_name: Name of the stage being timed.
        """
        self.profiler = profiler
        self.stage_name = stage_name
        self.start_time: float = 0.0
        self.elapsed_ms: float = 0.0

    def __enter__(self) -> StageTimer:
        """Start timing."""
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Stop timing and record result."""
        end_time = time.perf_counter()
        self.elapsed_ms = (end_time - self.start_time) * 1000
        self.profiler._record_stage_time(self.stage_name, self.elapsed_ms)


class PipelineProfiler:
    """Profiler for the D4V detection pipeline.

    Tracks timing for each pipeline stage and identifies bottlenecks.

    Example:
        profiler = PipelineProfiler(fps_target=30.0)

        # Profile pipeline execution
        with profiler.track_frame():
            with profiler.time_stage("color_mask"):
                mask = build_combat_text_mask(image)
            with profiler.time_stage("segmentation"):
                components = segment_damage_tokens(mask)
            with profiler.time_stage("ocr"):
                results = ocr_pil_image(crop)

        # Get results
        profile = profiler.get_profile()
        print(f"Bottleneck: {profile.bottlenecks}")
        print(f"Recommendations: {profile.recommendations}")
    """

    def __init__(
        self,
        session_id: str | None = None,
        fps_target: float | None = 30.0,
        enable_memory_tracking: bool = False,
    ) -> None:
        """Initialize pipeline profiler.

        Args:
            session_id: Session identifier. Auto-generated if not provided.
            fps_target: Target FPS for performance comparison.
            enable_memory_tracking: Enable memory usage tracking (requires psutil).
        """
        self.session_id = session_id or f"profile_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.fps_target = fps_target
        self.enable_memory_tracking = enable_memory_tracking

        # Timing data
        self.stage_times: dict[str, list[float]] = defaultdict(list)
        self.frame_times: list[float] = []
        self.start_time = datetime.now().isoformat()
        self.end_time: str | None = None

        # Frame tracking
        self.total_frames = 0
        self.start_timestamp = time.time()

        # Memory tracking
        self.memory_samples: list[float] = []

    def time_stage(self, stage_name: str) -> StageTimer:
        """Create a timer for a pipeline stage.

        Args:
            stage_name: Name of the stage.

        Returns:
            StageTimer context manager.
        """
        return StageTimer(self, stage_name)

    def track_frame(self) -> FrameTracker:
        """Create a frame-level tracker.

        Returns:
            FrameTracker context manager.
        """
        return FrameTracker(self)

    def _record_stage_time(self, stage_name: str, elapsed_ms: float) -> None:
        """Record stage execution time.

        Args:
            stage_name: Stage name.
            elapsed_ms: Elapsed time in milliseconds.
        """
        self.stage_times[stage_name].append(elapsed_ms)

    def _record_frame_time(self, elapsed_ms: float) -> None:
        """Record frame execution time.

        Args:
            elapsed_ms: Elapsed time in milliseconds.
        """
        self.frame_times.append(elapsed_ms)
        self.total_frames += 1

    def _record_memory(self, memory_mb: float) -> None:
        """Record memory usage sample.

        Args:
            memory_mb: Memory usage in megabytes.
        """
        self.memory_samples.append(memory_mb)

    def get_memory_usage(self) -> float | None:
        """Get current memory usage in MB.

        Returns:
            Memory usage in MB, or None if tracking disabled.
        """
        if not self.enable_memory_tracking:
            return None

        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / (1024 * 1024)
        except ImportError:
            return None

    def _calculate_percentile(self, data: list[float], percentile: float) -> float:
        """Calculate percentile of data.

        Args:
            data: List of values.
            percentile: Percentile to calculate (0-100).

        Returns:
            Percentile value.
        """
        if not data:
            return 0.0

        sorted_data = sorted(data)
        k = (len(sorted_data) - 1) * (percentile / 100)
        f = int(k)
        c = f + 1

        if c >= len(sorted_data):
            return sorted_data[-1]

        return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])

    def _calculate_std_dev(self, data: list[float], mean: float) -> float:
        """Calculate standard deviation.

        Args:
            data: List of values.
            mean: Mean of the values.

        Returns:
            Standard deviation.
        """
        if len(data) < 2:
            return 0.0

        variance = sum((x - mean) ** 2 for x in data) / len(data)
        return variance ** 0.5

    def get_profile(self) -> PipelineProfile:
        """Get complete profiling results.

        Returns:
            PipelineProfile with all profiling data.
        """
        # Calculate stage profiles
        stage_profiles: dict[str, StageProfile] = {}
        total_pipeline_time = 0.0

        for stage_name, times in self.stage_times.items():
            if not times:
                continue

            total_time = sum(times)
            total_pipeline_time += total_time
            mean_time = total_time / len(times)

            profile = StageProfile(
                name=stage_name,
                call_count=len(times),
                total_time_ms=total_time,
                min_time_ms=min(times),
                max_time_ms=max(times),
                mean_time_ms=mean_time,
                p50_time_ms=self._calculate_percentile(times, 50),
                p95_time_ms=self._calculate_percentile(times, 95),
                p99_time_ms=self._calculate_percentile(times, 99),
                std_dev_ms=self._calculate_std_dev(times, mean_time),
            )
            stage_profiles[stage_name] = profile

        # Calculate overall metrics
        elapsed = time.time() - self.start_timestamp
        fps_achieved = self.total_frames / elapsed if elapsed > 0 else 0.0

        # Calculate overhead
        total_frame_time = sum(self.frame_times)
        overhead_time = total_frame_time - total_pipeline_time

        # Identify bottlenecks
        bottlenecks = []
        recommendations = []

        if stage_profiles:
            slowest_stage = max(stage_profiles.values(), key=lambda p: p.total_time_ms)
            if slowest_stage.total_time_ms > total_pipeline_time * 0.5:
                bottlenecks.append(f"{slowest_stage.name} ({slowest_stage.percentage_of_total:.1f}% of pipeline)")
                recommendations.append(f"Optimize {slowest_stage.name} - it consumes {slowest_stage.percentage_of_total:.1f}% of pipeline time")

            # Check for high variance stages
            for stage in stage_profiles.values():
                if stage.std_dev_ms > stage.mean_time_ms * 0.5:
                    bottlenecks.append(f"{stage.name} (high variance: σ={stage.std_dev_ms:.1f}ms)")
                    recommendations.append(f"Reduce variance in {stage.name} for more consistent performance")

        # Check FPS
        if self.fps_target and fps_achieved < self.fps_target * 0.9:
            bottlenecks.append(f"FPS below target ({fps_achieved:.1f} vs {self.fps_target})")
            recommendations.append(f"Target {self.fps_target} FPS, achieving {fps_achieved:.1f} FPS")

        # Check for slow P99
        for stage in stage_profiles.values():
            if stage.p99_time_ms > stage.mean_time_ms * 3:
                recommendations.append(f"Investigate {stage.name} P99 spikes ({stage.p99_time_ms:.1f}ms vs {stage.mean_time_ms:.1f}ms mean)")

        profile = PipelineProfile(
            session_id=self.session_id,
            start_time=self.start_time,
            end_time=self.end_time,
            total_frames=self.total_frames,
            total_time_seconds=elapsed,
            stages=stage_profiles,
            pipeline_time_ms=total_pipeline_time,
            overhead_time_ms=max(0, overhead_time),
            fps_achieved=fps_achieved,
            fps_target=self.fps_target,
            bottlenecks=bottlenecks,
            recommendations=recommendations,
        )

        return profile

    def finalize(self) -> PipelineProfile:
        """Finalize profiling and return results.

        Returns:
            Final PipelineProfile object.
        """
        self.end_time = datetime.now().isoformat()
        return self.get_profile()

    def print_summary(self) -> None:
        """Print profiling summary to console."""
        profile = self.finalize()

        print(f"\n{'='*70}")
        print(f"Pipeline Profile: {self.session_id}")
        print(f"{'='*70}")
        print(f"Total frames: {profile.total_frames}")
        print(f"Total time: {profile.total_time_seconds:.2f}s")
        print(f"FPS achieved: {profile.fps_achieved:.1f}", end="")
        if self.fps_target:
            print(f" (target: {self.fps_target})")
        else:
            print()
        print()

        print("Stage Breakdown:")
        print(f"{'Stage':<25} {'Count':>8} {'Total(ms)':>12} {'Mean(ms)':>10} {'P95(ms)':>10} {'P99(ms)':>10}")
        print("-" * 70)

        # Sort by total time (descending)
        sorted_stages = sorted(profile.stages.values(), key=lambda p: p.total_time_ms, reverse=True)
        for stage in sorted_stages:
            print(f"{stage.name:<25} {stage.call_count:>8} {stage.total_time_ms:>12.2f} {stage.mean_time_ms:>10.2f} {stage.p95_time_ms:>10.2f} {stage.p99_time_ms:>10.2f}")

        print("-" * 70)
        print(f"{'Pipeline Total':<25} {'':>8} {profile.pipeline_time_ms:>12.2f}")
        print(f"{'Overhead':<25} {'':>8} {profile.overhead_time_ms:>12.2f}")
        print()

        if profile.bottlenecks:
            print("Bottlenecks:")
            for bottleneck in profile.bottlenecks:
                print(f"  ⚠ {bottleneck}")
            print()

        if profile.recommendations:
            print("Recommendations:")
            for rec in profile.recommendations:
                print(f"  • {rec}")
            print()

        print(f"{'='*70}\n")

    def export_report(self, output_path: Path | str) -> None:
        """Export profiling report to JSON file.

        Args:
            output_path: Path to output file.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        profile = self.finalize()
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(profile.to_json())

    def reset(self) -> None:
        """Reset profiler state."""
        self.stage_times.clear()
        self.frame_times.clear()
        self.memory_samples.clear()
        self.total_frames = 0
        self.start_timestamp = time.time()
        self.start_time = datetime.now().isoformat()
        self.end_time = None


class FrameTracker:
    """Context manager for tracking frame-level timing.

    Example:
        profiler = PipelineProfiler()

        with profiler.track_frame():
            # Process frame
            process_frame(image)
    """

    def __init__(self, profiler: PipelineProfiler) -> None:
        """Initialize frame tracker.

        Args:
            profiler: Parent profiler instance.
        """
        self.profiler = profiler
        self.start_time: float = 0.0

    def __enter__(self) -> FrameTracker:
        """Start timing."""
        self.start_time = time.perf_counter()

        # Track memory if enabled
        if self.profiler.enable_memory_tracking:
            memory = self.profiler.get_memory_usage()
            if memory is not None:
                self.profiler._record_memory(memory)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Stop timing and record result."""
        end_time = time.perf_counter()
        elapsed_ms = (end_time - self.start_time) * 1000
        self.profiler._record_frame_time(elapsed_ms)


def profile_pipeline(
    func: Callable,
    *args: Any,
    session_id: str | None = None,
    fps_target: float | None = 30.0,
    **kwargs: Any,
) -> tuple[Any, PipelineProfile]:
    """Decorator-style profiling for pipeline execution.

    Example:
        result, profile = profile_pipeline(
            run_detection_pipeline,
            image,
            session_id="test_run",
            fps_target=30.0,
        )

    Args:
        func: Function to profile.
        *args: Arguments to pass to function.
        session_id: Session identifier.
        fps_target: Target FPS.
        **kwargs: Keyword arguments to pass to function.

    Returns:
        Tuple of (function result, PipelineProfile).
    """
    profiler = PipelineProfiler(
        session_id=session_id,
        fps_target=fps_target,
    )

    with profiler.track_frame():
        result = func(*args, **kwargs)

    profile = profiler.finalize()
    return result, profile
