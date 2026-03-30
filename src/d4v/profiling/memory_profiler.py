"""Memory profiling for the detection pipeline.

Tracks memory usage patterns and identifies memory-intensive operations.
"""

from __future__ import annotations

import gc
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MemorySnapshot:
    """Memory usage snapshot at a point in time.

    Attributes:
        timestamp: ISO 8601 timestamp.
        frame_index: Frame index when snapshot was taken.
        stage: Pipeline stage name.
        rss_mb: Resident set size in megabytes.
        vms_mb: Virtual memory size in megabytes.
        percent: Memory usage as percentage of system total.
    """

    timestamp: str
    frame_index: int
    stage: str
    rss_mb: float
    vms_mb: float
    percent: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp,
            "frame_index": self.frame_index,
            "stage": self.stage,
            "rss_mb": round(self.rss_mb, 2),
            "vms_mb": round(self.vms_mb, 2),
            "percent": round(self.percent, 2),
        }


@dataclass
class MemoryProfile:
    """Memory profiling results.

    Attributes:
        session_id: Session identifier.
        start_time: Profiling start timestamp.
        end_time: Profiling end timestamp.
        total_frames: Total frames processed.
        snapshots: Memory snapshots throughout execution.
        peak_rss_mb: Peak RSS memory usage.
        avg_rss_mb: Average RSS memory usage.
        min_rss_mb: Minimum RSS memory usage.
        rss_growth_mb: Memory growth from start to end.
        gc_collections: Number of garbage collections triggered.
        memory_leaks: Suspected memory leak indicators.
        recommendations: Memory optimization recommendations.
    """

    session_id: str
    start_time: str
    end_time: str | None = None
    total_frames: int = 0
    snapshots: list[MemorySnapshot] = field(default_factory=list)
    peak_rss_mb: float = 0.0
    avg_rss_mb: float = 0.0
    min_rss_mb: float = 0.0
    rss_growth_mb: float = 0.0
    gc_collections: int = 0
    memory_leaks: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "total_frames": self.total_frames,
            "snapshots": [s.to_dict() for s in self.snapshots],
            "peak_rss_mb": round(self.peak_rss_mb, 2),
            "avg_rss_mb": round(self.avg_rss_mb, 2),
            "min_rss_mb": round(self.min_rss_mb, 2),
            "rss_growth_mb": round(self.rss_growth_mb, 2),
            "gc_collections": self.gc_collections,
            "memory_leaks": self.memory_leaks,
            "recommendations": self.recommendations,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


class MemoryProfiler:
    """Memory profiler for the D4V detection pipeline.

    Tracks memory usage across pipeline stages and identifies
    memory-intensive operations and potential leaks.

    Example:
        profiler = MemoryProfiler(session_id="session_001")

        # Track memory at different points
        profiler.snapshot("start", frame=0)
        mask = build_combat_text_mask(image)
        profiler.snapshot("after_mask", frame=0)

        # Get results
        profile = profiler.finalize()
        print(f"Peak memory: {profile.peak_rss_mb:.1f} MB")
        print(f"Memory growth: {profile.rss_growth_mb:.1f} MB")
    """

    def __init__(
        self,
        session_id: str | None = None,
        track_gc: bool = True,
        snapshot_interval: int = 1,
    ) -> None:
        """Initialize memory profiler.

        Args:
            session_id: Session identifier. Auto-generated if not provided.
            track_gc: Enable garbage collection tracking.
            snapshot_interval: Take snapshot every N frames.
        """
        self.session_id = session_id or f"memory_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.track_gc = track_gc
        self.snapshot_interval = snapshot_interval

        # Memory tracking
        self.snapshots: list[MemorySnapshot] = []
        self.start_time = datetime.now().isoformat()
        self.end_time: str | None = None

        # GC tracking
        self.gc_counts: dict[int, int] = {0: 0, 1: 0, 2: 0}
        self.gc_collections = 0

        # Baseline
        self.baseline_rss: float | None = None
        self.frame_count = 0

    def get_memory_info(self) -> tuple[float, float, float]:
        """Get current memory information.

        Returns:
            Tuple of (rss_mb, vms_mb, percent).
        """
        try:
            import psutil
            process = psutil.Process()
            memory = process.memory_info()
            system_memory = psutil.virtual_memory()

            rss_mb = memory.rss / (1024 * 1024)
            vms_mb = memory.vms / (1024 * 1024)
            percent = memory.percent

            return rss_mb, vms_mb, percent
        except ImportError:
            # Fallback without psutil
            return 0.0, 0.0, 0.0

    def snapshot(
        self,
        stage: str,
        frame_index: int,
    ) -> MemorySnapshot | None:
        """Take a memory snapshot.

        Args:
            stage: Pipeline stage name.
            frame_index: Current frame index.

        Returns:
            MemorySnapshot if successful, None if psutil not available.
        """
        rss_mb, vms_mb, percent = self.get_memory_info()

        if rss_mb == 0.0:
            return None

        snapshot = MemorySnapshot(
            timestamp=datetime.now().isoformat(),
            frame_index=frame_index,
            stage=stage,
            rss_mb=rss_mb,
            vms_mb=vms_mb,
            percent=percent,
        )

        self.snapshots.append(snapshot)
        self.frame_count = frame_index + 1

        # Set baseline
        if self.baseline_rss is None:
            self.baseline_rss = rss_mb

        # Track GC
        if self.track_gc:
            current_gc = gc.get_count()
            for gen in range(3):
                if current_gc[gen] > self.gc_counts[gen]:
                    self.gc_collections += 1
                    self.gc_counts[gen] = current_gc[gen]

        return snapshot

    def force_gc(self) -> int:
        """Force garbage collection and return freed memory.

        Returns:
            Approximate memory freed in MB (requires psutil).
        """
        before = self.get_memory_info()[0]
        collected = gc.collect()
        after = self.get_memory_info()[0]

        freed = before - after
        return max(0, freed)

    def _analyze_memory_trends(self) -> tuple[list[str], list[str]]:
        """Analyze memory usage trends.

        Returns:
            Tuple of (memory_leaks, recommendations).
        """
        leaks: list[str] = []
        recommendations: list[str] = []

        if len(self.snapshots) < 10:
            return leaks, recommendations

        # Check for memory growth
        if self.baseline_rss is not None and self.snapshots:
            latest_rss = self.snapshots[-1].rss_mb
            growth = latest_rss - self.baseline_rss

            if growth > 50:  # More than 50MB growth
                leaks.append(f"Memory growth detected: {growth:.1f} MB")
                recommendations.append("Investigate objects not being garbage collected")

        # Check for stage-specific memory spikes
        stage_memory: dict[str, list[float]] = {}
        for snapshot in self.snapshots:
            if snapshot.stage not in stage_memory:
                stage_memory[snapshot.stage] = []
            stage_memory[snapshot.stage].append(snapshot.rss_mb)

        for stage, memory_values in stage_memory.items():
            if len(memory_values) > 1:
                avg_memory = sum(memory_values) / len(memory_values)
                max_memory = max(memory_values)

                if max_memory > avg_memory * 1.5:
                    recommendations.append(
                        f"Stage '{stage}' has memory spikes (avg: {avg_memory:.1f} MB, max: {max_memory:.1f} MB)"
                    )

        # Check GC frequency
        if self.gc_collections > self.frame_count * 0.5:
            recommendations.append(
                f"High GC frequency ({self.gc_collections} collections in {self.frame_count} frames) - consider object pooling"
            )

        return leaks, recommendations

    def finalize(self) -> MemoryProfile:
        """Finalize memory profiling and return results.

        Returns:
            MemoryProfile with all profiling data.
        """
        self.end_time = datetime.now().isoformat()

        # Calculate statistics
        if self.snapshots:
            rss_values = [s.rss_mb for s in self.snapshots]
            peak_rss = max(rss_values)
            avg_rss = sum(rss_values) / len(rss_values)
            min_rss = min(rss_values)

            if self.baseline_rss is not None:
                rss_growth = rss_values[-1] - self.baseline_rss
            else:
                rss_growth = 0.0
        else:
            peak_rss = avg_rss = min_rss = rss_growth = 0.0

        # Analyze trends
        leaks, recommendations = self._analyze_memory_trends()

        profile = MemoryProfile(
            session_id=self.session_id,
            start_time=self.start_time,
            end_time=self.end_time,
            total_frames=self.frame_count,
            snapshots=self.snapshots,
            peak_rss_mb=peak_rss,
            avg_rss_mb=avg_rss,
            min_rss_mb=min_rss,
            rss_growth_mb=rss_growth,
            gc_collections=self.gc_collections,
            memory_leaks=leaks,
            recommendations=recommendations,
        )

        return profile

    def print_summary(self) -> None:
        """Print memory profiling summary to console."""
        profile = self.finalize()

        print(f"\n{'='*70}")
        print(f"Memory Profile: {self.session_id}")
        print(f"{'='*70}")
        print(f"Total frames: {profile.total_frames}")
        print(f"GC collections: {profile.gc_collections}")
        print()

        print("Memory Statistics:")
        print(f"  Peak RSS:     {profile.peak_rss_mb:>10.1f} MB")
        print(f"  Average RSS:  {profile.avg_rss_mb:>10.1f} MB")
        print(f"  Minimum RSS:  {profile.min_rss_mb:>10.1f} MB")
        print(f"  Growth:       {profile.rss_growth_mb:>10.1f} MB")
        print()

        if profile.memory_leaks:
            print("⚠ Memory Leaks:")
            for leak in profile.memory_leaks:
                print(f"  • {leak}")
            print()

        if profile.recommendations:
            print("Recommendations:")
            for rec in profile.recommendations:
                print(f"  • {rec}")
            print()

        # Stage breakdown
        if profile.snapshots:
            stage_stats: dict[str, dict[str, float]] = {}
            for snapshot in profile.snapshots:
                if snapshot.stage not in stage_stats:
                    stage_stats[snapshot.stage] = {
                        "count": 0,
                        "total": 0.0,
                        "max": 0.0,
                    }
                stage_stats[snapshot.stage]["count"] += 1
                stage_stats[snapshot.stage]["total"] += snapshot.rss_mb
                stage_stats[snapshot.stage]["max"] = max(
                    stage_stats[snapshot.stage]["max"], snapshot.rss_mb
                )

            print("Stage Memory Usage:")
            print(f"{'Stage':<25} {'Samples':>10} {'Avg(MB)':>12} {'Max(MB)':>12}")
            print("-" * 60)
            for stage, stats in sorted(stage_stats.items(), key=lambda x: x[1]["total"], reverse=True):
                avg = stats["total"] / stats["count"]
                print(f"{stage:<25} {stats['count']:>10} {avg:>12.1f} {stats['max']:>12.1f}")
            print()

        print(f"{'='*70}\n")

    def export_report(self, output_path: Path | str) -> None:
        """Export memory profiling report to JSON file.

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
        self.snapshots.clear()
        self.gc_counts = {0: 0, 1: 0, 2: 0}
        self.gc_collections = 0
        self.baseline_rss = None
        self.frame_count = 0
        self.start_time = datetime.now().isoformat()
        self.end_time = None
