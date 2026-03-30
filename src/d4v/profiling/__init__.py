"""Profiling infrastructure for D4V performance analysis.

This package provides:
- Pipeline stage timing and bottleneck identification
- Memory usage tracking and leak detection
- Performance reporting and optimization recommendations

Example:
    from d4v.profiling import PipelineProfiler, MemoryProfiler

    # Profile pipeline timing
    profiler = PipelineProfiler(session_id="test", fps_target=30.0)

    with profiler.track_frame():
        with profiler.time_stage("color_mask"):
            mask = build_combat_text_mask(image)
        with profiler.time_stage("segmentation"):
            components = segment_damage_tokens(mask)

    profiler.print_summary()
    profiler.export_report("profile_results.json")

    # Profile memory usage
    memory_profiler = MemoryProfiler(session_id="test")
    memory_profiler.snapshot("start", frame=0)
    # ... process ...
    memory_profiler.snapshot("end", frame=100)
    memory_profiler.print_summary()
"""

from d4v.profiling.memory_profiler import (
    MemoryProfile,
    MemoryProfiler,
    MemorySnapshot,
)
from d4v.profiling.pipeline_profiler import (
    FrameTracker,
    PipelineProfile,
    PipelineProfiler,
    StageTimer,
    profile_pipeline,
)

__all__ = [
    # Pipeline Profiler
    "PipelineProfiler",
    "PipelineProfile",
    "StageTimer",
    "FrameTracker",
    "profile_pipeline",
    # Memory Profiler
    "MemoryProfiler",
    "MemoryProfile",
    "MemorySnapshot",
]
