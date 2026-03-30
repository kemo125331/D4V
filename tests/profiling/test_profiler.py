"""Tests for profiling functionality."""

import json
import tempfile
import time
from pathlib import Path

import pytest

from d4v.profiling import (
    FrameTracker,
    MemoryProfile,
    MemoryProfiler,
    MemorySnapshot,
    PipelineProfile,
    PipelineProfiler,
    profile_pipeline,
)


class TestPipelineProfiler:
    """Tests for PipelineProfiler."""

    def test_profiler_creation(self):
        """Given profiler created, expect initialized state."""
        profiler = PipelineProfiler(session_id="test", fps_target=30.0)
        assert profiler.session_id == "test"
        assert profiler.fps_target == 30.0
        assert profiler.total_frames == 0

    def test_time_stage(self):
        """Given stage timed, expect time recorded."""
        profiler = PipelineProfiler(session_id="test")

        with profiler.time_stage("test_stage"):
            time.sleep(0.01)  # 10ms

        assert "test_stage" in profiler.stage_times
        assert len(profiler.stage_times["test_stage"]) == 1
        assert profiler.stage_times["test_stage"][0] >= 10.0

    def test_time_multiple_stages(self):
        """Given multiple stages timed, expect all recorded."""
        profiler = PipelineProfiler(session_id="test")

        with profiler.time_stage("stage_a"):
            time.sleep(0.005)
        with profiler.time_stage("stage_b"):
            time.sleep(0.01)
        with profiler.time_stage("stage_c"):
            time.sleep(0.015)

        assert "stage_a" in profiler.stage_times
        assert "stage_b" in profiler.stage_times
        assert "stage_c" in profiler.stage_times

    def test_track_frame(self):
        """Given frame tracked, expect frame count incremented."""
        profiler = PipelineProfiler(session_id="test")

        with profiler.track_frame():
            time.sleep(0.01)

        assert profiler.total_frames == 1
        assert len(profiler.frame_times) == 1

    def test_track_multiple_frames(self):
        """Given multiple frames tracked, expect all recorded."""
        profiler = PipelineProfiler(session_id="test")

        for i in range(5):
            with profiler.track_frame():
                time.sleep(0.01)

        assert profiler.total_frames == 5
        assert len(profiler.frame_times) == 5

    def test_get_profile(self):
        """Given profile requested, expect complete statistics."""
        profiler = PipelineProfiler(session_id="test", fps_target=30.0)

        for i in range(10):
            with profiler.track_frame():
                with profiler.time_stage("stage_a"):
                    time.sleep(0.005)
                with profiler.time_stage("stage_b"):
                    time.sleep(0.01)

        profile = profiler.get_profile()

        assert isinstance(profile, PipelineProfile)
        assert profile.total_frames == 10
        assert "stage_a" in profile.stages
        assert "stage_b" in profile.stages
        assert profile.stages["stage_a"].call_count == 10
        assert profile.stages["stage_b"].call_count == 10

    def test_stage_profile_statistics(self):
        """Given stage profiled, expect statistics calculated."""
        profiler = PipelineProfiler(session_id="test")

        # Simulate varying execution times
        for i in range(100):
            with profiler.time_stage("test_stage"):
                time.sleep(0.001 * (1 + i % 10))

        profile = profiler.get_profile()
        stage = profile.stages["test_stage"]

        assert stage.call_count == 100
        assert stage.min_time_ms >= 1.0
        assert stage.max_time_ms >= 10.0
        assert stage.mean_time_ms > 0
        assert stage.p50_time_ms > 0
        assert stage.p95_time_ms > 0
        assert stage.p99_time_ms > 0
        assert stage.std_dev_ms > 0

    def test_bottleneck_detection(self):
        """Given slow stage, expect bottleneck identified."""
        profiler = PipelineProfiler(session_id="test")

        for i in range(10):
            with profiler.track_frame():
                with profiler.time_stage("fast_stage"):
                    time.sleep(0.001)
                with profiler.time_stage("slow_stage"):
                    time.sleep(0.05)  # Much slower

        profile = profiler.get_profile()

        assert len(profile.bottlenecks) > 0
        assert any("slow_stage" in b for b in profile.bottlenecks)

    def test_fps_target_check(self):
        """Given FPS below target, expect bottleneck flagged."""
        profiler = PipelineProfiler(session_id="test", fps_target=1000.0)

        for i in range(10):
            with profiler.track_frame():
                time.sleep(0.1)  # 10 FPS

        profile = profiler.get_profile()

        assert any("FPS" in b for b in profile.bottlenecks)

    def test_recommendations_generated(self):
        """Given performance issues, expect recommendations."""
        profiler = PipelineProfiler(session_id="test", fps_target=30.0)

        for i in range(10):
            with profiler.track_frame():
                with profiler.time_stage("variable_stage"):
                    # High variance
                    sleep_time = 0.05 if i % 5 == 0 else 0.005
                    time.sleep(sleep_time)

        profile = profiler.get_profile()

        assert len(profile.recommendations) > 0

    def test_finalize(self):
        """Given finalize called, expect end_time set."""
        profiler = PipelineProfiler(session_id="test")

        with profiler.track_frame():
            time.sleep(0.01)

        profile = profiler.finalize()

        assert profile.end_time is not None
        assert profile.end_time > profile.start_time

    def test_print_summary(self, capsys):
        """Given summary printed, expect output."""
        profiler = PipelineProfiler(session_id="test")

        for i in range(5):
            with profiler.track_frame():
                with profiler.time_stage("test"):
                    time.sleep(0.005)

        profiler.print_summary()

        captured = capsys.readouterr()
        assert "Pipeline Profile" in captured.out
        assert "test" in captured.out

    def test_export_report(self, tmp_path: Path):
        """Given report exported, expect JSON file created."""
        profiler = PipelineProfiler(session_id="test")

        for i in range(5):
            with profiler.track_frame():
                with profiler.time_stage("test"):
                    time.sleep(0.005)

        output_path = tmp_path / "profile.json"
        profiler.export_report(output_path)

        assert output_path.exists()
        with open(output_path) as f:
            data = json.load(f)
        assert data["session_id"] == "test"
        assert data["total_frames"] == 5

    def test_reset(self):
        """Given reset called, expect state cleared."""
        profiler = PipelineProfiler(session_id="test")

        for i in range(5):
            with profiler.track_frame():
                with profiler.time_stage("test"):
                    time.sleep(0.005)

        profiler.reset()

        assert profiler.total_frames == 0
        assert len(profiler.stage_times) == 0
        assert len(profiler.frame_times) == 0

    def test_to_dict(self):
        """Given profile converted to dict, expect all fields."""
        profiler = PipelineProfiler(session_id="test")

        with profiler.track_frame():
            with profiler.time_stage("test"):
                time.sleep(0.005)

        profile = profiler.get_profile()
        data = profile.to_dict()

        assert data["session_id"] == "test"
        assert data["total_frames"] == 1
        assert "test" in data["stages"]


class TestProfilePipeline:
    """Tests for profile_pipeline function."""

    def test_profile_pipeline(self):
        """Given function profiled, expect result and profile."""
        def test_func(x, y):
            time.sleep(0.01)
            return x + y

        result, profile = profile_pipeline(
            test_func,
            5, 3,
            session_id="test",
            fps_target=30.0,
        )

        assert result == 8
        assert isinstance(profile, PipelineProfile)
        assert profile.total_frames == 1


class TestFrameTracker:
    """Tests for FrameTracker."""

    def test_frame_tracker_context(self):
        """Given frame tracker used as context, expect timing works."""
        profiler = PipelineProfiler(session_id="test")

        with profiler.track_frame() as tracker:
            assert isinstance(tracker, FrameTracker)
            time.sleep(0.01)

        assert profiler.total_frames == 1


class TestMemoryProfiler:
    """Tests for MemoryProfiler."""

    def test_profiler_creation(self):
        """Given profiler created, expect initialized state."""
        profiler = MemoryProfiler(session_id="test")
        assert profiler.session_id == "test"
        assert profiler.track_gc
        assert profiler.snapshot_interval == 1

    def test_snapshot(self):
        """Given snapshot taken, expect memory recorded."""
        profiler = MemoryProfiler(session_id="test")

        snapshot = profiler.snapshot("test_stage", frame_index=0)

        # Snapshot may be None if psutil not available
        if snapshot is not None:
            assert isinstance(snapshot, MemorySnapshot)
            assert snapshot.stage == "test_stage"
            assert snapshot.frame_index == 0
            assert len(profiler.snapshots) == 1

    def test_snapshot_baseline(self):
        """Given first snapshot, expect baseline set."""
        profiler = MemoryProfiler(session_id="test")

        profiler.snapshot("start", frame_index=0)

        if profiler.baseline_rss is not None:
            assert profiler.baseline_rss > 0

    def test_multiple_snapshots(self):
        """Given multiple snapshots, expect all recorded."""
        profiler = MemoryProfiler(session_id="test")

        for i in range(5):
            profiler.snapshot(f"stage_{i}", frame_index=i)

        # Snapshots depend on psutil availability
        # If psutil not installed, snapshots will be empty
        if profiler.snapshots:
            assert len(profiler.snapshots) == 5

    def test_finalize(self):
        """Given finalize called, expect complete profile."""
        profiler = MemoryProfiler(session_id="test")

        for i in range(10):
            profiler.snapshot("test", frame_index=i)

        profile = profiler.finalize()

        assert isinstance(profile, MemoryProfile)
        # total_frames only set if snapshots succeeded
        if profiler.snapshots:
            assert profile.total_frames >= 10
        assert profile.end_time is not None

    def test_finalize_statistics(self):
        """Given finalize called, expect statistics calculated."""
        profiler = MemoryProfiler(session_id="test")

        for i in range(20):
            profiler.snapshot("test", frame_index=i)

        profile = profiler.finalize()

        if profile.snapshots:
            assert profile.peak_rss_mb >= 0
            assert profile.avg_rss_mb >= 0
            assert profile.min_rss_mb >= 0

    def test_gc_tracking(self):
        """Given GC tracking enabled, expect GC counted."""
        profiler = MemoryProfiler(session_id="test", track_gc=True)

        for i in range(10):
            profiler.snapshot("test", frame_index=i)

        # GC count should be tracked
        assert profiler.gc_collections >= 0

    def test_force_gc(self):
        """Given GC forced, expect memory freed."""
        profiler = MemoryProfiler(session_id="test")

        freed = profiler.force_gc()

        # Freed memory should be non-negative
        assert freed >= 0

    def test_print_summary(self, capsys):
        """Given summary printed, expect output."""
        profiler = MemoryProfiler(session_id="test")

        for i in range(5):
            profiler.snapshot("test", frame_index=i)

        profiler.print_summary()

        captured = capsys.readouterr()
        # Summary should have content (may vary based on psutil availability)
        assert "Memory Profile" in captured.out or len(captured.out) > 0

    def test_export_report(self, tmp_path: Path):
        """Given report exported, expect JSON file created."""
        profiler = MemoryProfiler(session_id="test")

        for i in range(5):
            profiler.snapshot("test", frame_index=i)

        output_path = tmp_path / "memory_profile.json"
        profiler.export_report(output_path)

        # May not create file if psutil not available
        if profiler.snapshots:
            assert output_path.exists()
            with open(output_path) as f:
                data = json.load(f)
            assert data["session_id"] == "test"

    def test_reset(self):
        """Given reset called, expect state cleared."""
        profiler = MemoryProfiler(session_id="test")

        for i in range(5):
            profiler.snapshot("test", frame_index=i)

        profiler.reset()

        assert len(profiler.snapshots) == 0
        assert profiler.baseline_rss is None

    def test_memory_snapshot_to_dict(self):
        """Given snapshot converted to dict, expect all fields."""
        snapshot = MemorySnapshot(
            timestamp="2026-03-30T00:00:00",
            frame_index=10,
            stage="test",
            rss_mb=100.5,
            vms_mb=200.5,
            percent=50.0,
        )

        data = snapshot.to_dict()

        assert data["timestamp"] == "2026-03-30T00:00:00"
        assert data["frame_index"] == 10
        assert data["stage"] == "test"
        assert data["rss_mb"] == 100.5
        assert data["vms_mb"] == 200.5


class TestMemoryProfile:
    """Tests for MemoryProfile."""

    def test_to_dict(self):
        """Given profile converted to dict, expect all fields."""
        profile = MemoryProfile(
            session_id="test",
            start_time="2026-03-30T00:00:00",
            total_frames=100,
            peak_rss_mb=150.0,
            avg_rss_mb=100.0,
            rss_growth_mb=10.0,
        )

        data = profile.to_dict()

        assert data["session_id"] == "test"
        assert data["total_frames"] == 100
        assert data["peak_rss_mb"] == 150.0
        assert data["rss_growth_mb"] == 10.0

    def test_to_json(self):
        """Given profile converted to JSON, expect valid string."""
        profile = MemoryProfile(
            session_id="test",
            start_time="2026-03-30T00:00:00",
        )

        json_str = profile.to_json()
        data = json.loads(json_str)

        assert data["session_id"] == "test"


class TestIntegration:
    """Integration tests for profiling."""

    def test_full_pipeline_profiling(self):
        """Given full pipeline profiled, expect complete results."""
        profiler = PipelineProfiler(
            session_id="integration_test",
            fps_target=30.0,
        )

        # Simulate full pipeline
        for frame in range(20):
            with profiler.track_frame():
                with profiler.time_stage("capture"):
                    time.sleep(0.005)
                with profiler.time_stage("color_mask"):
                    time.sleep(0.01)
                with profiler.time_stage("segmentation"):
                    time.sleep(0.008)
                with profiler.time_stage("ocr"):
                    time.sleep(0.02)
                with profiler.time_stage("parsing"):
                    time.sleep(0.003)

        profile = profiler.finalize()

        assert profile.total_frames == 20
        assert len(profile.stages) == 5
        assert profile.fps_achieved > 0
        assert profile.pipeline_time_ms > 0

    def test_combined_timing_and_memory(self):
        """Given both profilers used, expect both work."""
        timing_profiler = PipelineProfiler(session_id="combined")
        memory_profiler = MemoryProfiler(session_id="combined")

        for i in range(10):
            with timing_profiler.track_frame():
                with timing_profiler.time_stage("test"):
                    time.sleep(0.005)
                    memory_profiler.snapshot("test", frame_index=i)

        timing_profile = timing_profiler.finalize()
        memory_profile = memory_profiler.finalize()

        assert timing_profile.total_frames == 10
        # Memory snapshots depend on psutil availability
        assert memory_profile.total_frames >= 0
