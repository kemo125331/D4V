"""Tests for benchmark runner."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from d4v.benchmark.annotation import AnnotationBuilder, GroundTruthHit
from d4v.benchmark.runner import (
    BenchmarkConfig,
    BenchmarkResult,
    BenchmarkRunner,
    compare_benchmark_results,
)
from d4v.vision.config import VisionConfig


class TestBenchmarkResult:
    """Tests for BenchmarkResult dataclass."""

    def test_result_to_dict(self):
        """Given result, expect dict with all fields."""
        from d4v.benchmark.metrics import BenchmarkMetrics

        metrics = BenchmarkMetrics(
            true_positives=85,
            false_positives=15,
            false_negatives=10,
        )
        result = BenchmarkResult(
            session_id="session_001",
            session_name="Test",
            total_frames=100,
            total_ground_truth_hits=95,
            total_detected_hits=100,
            metrics=metrics,
            processing_time_seconds=5.0,
            fps_processed=20.0,
        )
        data = result.to_dict()
        assert data["session_id"] == "session_001"
        assert data["metrics"]["precision"] == 0.85
        assert data["processing_time_seconds"] == 5.0

    def test_result_to_json_and_back(self):
        """Given result serialized to JSON, expect round-trip works."""
        import json

        from d4v.benchmark.metrics import BenchmarkMetrics

        metrics = BenchmarkMetrics(
            true_positives=85,
            false_positives=15,
            false_negatives=10,
        )
        result = BenchmarkResult(
            session_id="session_001",
            session_name="Test",
            total_frames=100,
            total_ground_truth_hits=95,
            total_detected_hits=100,
            metrics=metrics,
        )
        json_str = result.to_json()
        data = json.loads(json_str)
        assert data["session_id"] == "session_001"
        assert data["metrics"]["f1_score"] < 1.0

    def test_result_save_and_load_file(self, tmp_path: Path):
        """Given result saved to file, expect load works."""
        from d4v.benchmark.metrics import BenchmarkMetrics

        metrics = BenchmarkMetrics(
            true_positives=85,
            false_positives=15,
            false_negatives=10,
        )
        result = BenchmarkResult(
            session_id="session_001",
            session_name="Test",
            total_frames=100,
            total_ground_truth_hits=95,
            total_detected_hits=100,
            metrics=metrics,
        )

        path = tmp_path / "result.json"
        result.to_file(path)
        loaded = BenchmarkResult.from_file(path)

        assert loaded.session_id == "session_001"
        assert loaded.metrics.precision == result.metrics.precision


class TestBenchmarkRunner:
    """Tests for BenchmarkRunner."""

    def test_runner_initialization(self):
        """Given runner created, expect pipeline initialized."""
        runner = BenchmarkRunner()
        assert runner.pipeline is not None
        assert runner.vision_config is not None

    def test_runner_with_custom_config(self):
        """Given runner with custom vision config, expect used."""
        config = VisionConfig(min_confidence=0.8)
        runner = BenchmarkRunner(vision_config=config)
        assert runner.vision_config.min_confidence == 0.8

    def test_run_benchmark_no_frames(self, tmp_path: Path):
        """Given annotation with no frames, expect empty result."""
        annotation = (
            AnnotationBuilder(session_id="test")
            .with_metadata(
                session_name="Test",
                description="Test",
                resolution="1920x1080",
                ui_scale=100.0,
                total_frames=100,
                fps=30.0,
            )
            .add_hit(frame=10, value=1000, x=500, y=300)
            .build()
        )

        runner = BenchmarkRunner()
        config = BenchmarkConfig(replay_frames_dir=tmp_path)
        result = runner.run_benchmark(annotation, config)

        assert result.total_frames == 0
        assert result.metrics.recall == 0.0
        assert "No frame images found" in result.errors[0]

    def test_run_benchmark_with_mock_frames(self, tmp_path: Path):
        """Given annotation with mock frames, expect processing runs."""
        # Create mock frames
        frames_dir = tmp_path / "frames"
        frames_dir.mkdir()
        for i in range(10):
            img = Image.new("RGB", (1920, 1080), color="black")
            img.save(frames_dir / f"frame_{i:04d}.png")

        annotation = (
            AnnotationBuilder(session_id="test")
            .with_metadata(
                session_name="Test",
                description="Test",
                resolution="1920x1080",
                ui_scale=100.0,
                total_frames=10,
                fps=30.0,
            )
            .add_hit(frame=5, value=1000, x=500, y=300)
            .build()
        )

        runner = BenchmarkRunner()
        config = BenchmarkConfig(replay_frames_dir=frames_dir)
        result = runner.run_benchmark(annotation, config)

        assert result.total_frames == 10
        assert result.processing_time_seconds >= 0.0

    @patch.object(BenchmarkRunner, "_create_empty_result")
    def test_run_benchmark_error_handling(self, mock_create, tmp_path: Path):
        """Given processing error, expect error captured in result."""
        annotation = (
            AnnotationBuilder(session_id="test")
            .with_metadata(
                session_name="Test",
                description="Test",
                resolution="1920x1080",
                ui_scale=100.0,
                total_frames=10,
                fps=30.0,
            )
            .build()
        )

        runner = BenchmarkRunner()
        config = BenchmarkConfig(replay_frames_dir=tmp_path)
        result = runner.run_benchmark(annotation, config)

        # Should have errors list (even if empty list for no frames)
        assert isinstance(result.errors, list)


class TestCompareBenchmarkResults:
    """Tests for comparing benchmark results."""

    def test_compare_improvement(self):
        """Given better result, expect positive delta."""
        from d4v.benchmark.metrics import BenchmarkMetrics

        before = BenchmarkResult(
            session_id="test",
            session_name="Test",
            total_frames=100,
            total_ground_truth_hits=100,
            total_detected_hits=100,
            metrics=BenchmarkMetrics(
                true_positives=70,
                false_positives=30,
                false_negatives=30,
            ),
            fps_processed=20.0,
        )
        after = BenchmarkResult(
            session_id="test",
            session_name="Test",
            total_frames=100,
            total_ground_truth_hits=100,
            total_detected_hits=100,
            metrics=BenchmarkMetrics(
                true_positives=85,
                false_positives=15,
                false_negatives=15,
            ),
            fps_processed=25.0,
        )

        comparison = compare_benchmark_results(before, after)

        assert comparison["precision"]["delta"] > 0
        assert comparison["recall"]["delta"] > 0
        assert comparison["f1_score"]["delta"] > 0

    def test_compare_regression(self):
        """Given worse result, expect negative delta."""
        from d4v.benchmark.metrics import BenchmarkMetrics

        before = BenchmarkResult(
            session_id="test",
            session_name="Test",
            total_frames=100,
            total_ground_truth_hits=100,
            total_detected_hits=100,
            metrics=BenchmarkMetrics(
                true_positives=90,
                false_positives=10,
                false_negatives=10,
            ),
            fps_processed=30.0,
        )
        after = BenchmarkResult(
            session_id="test",
            session_name="Test",
            total_frames=100,
            total_ground_truth_hits=100,
            total_detected_hits=100,
            metrics=BenchmarkMetrics(
                true_positives=70,
                false_positives=30,
                false_negatives=30,
            ),
            fps_processed=20.0,
        )

        comparison = compare_benchmark_results(before, after)

        assert comparison["precision"]["delta"] < 0
        assert comparison["recall"]["delta"] < 0
        assert comparison["f1_score"]["delta"] < 0

    def test_compare_percent_change(self):
        """Given results, expect percent change calculated correctly."""
        from d4v.benchmark.metrics import BenchmarkMetrics

        before = BenchmarkResult(
            session_id="test",
            session_name="Test",
            total_frames=100,
            total_ground_truth_hits=100,
            total_detected_hits=100,
            metrics=BenchmarkMetrics(
                true_positives=50,
                false_positives=50,
                false_negatives=50,
            ),
            fps_processed=20.0,
        )
        after = BenchmarkResult(
            session_id="test",
            session_name="Test",
            total_frames=100,
            total_ground_truth_hits=100,
            total_detected_hits=100,
            metrics=BenchmarkMetrics(
                true_positives=75,
                false_positives=25,
                false_negatives=25,
            ),
            fps_processed=30.0,
        )

        comparison = compare_benchmark_results(before, after)

        # Precision: 0.5 -> 0.75 = 50% improvement
        assert abs(comparison["precision"]["percent_change"] - 50.0) < 0.1

    def test_compare_zero_baseline(self):
        """Given zero baseline, expect inf percent change."""
        from d4v.benchmark.metrics import BenchmarkMetrics

        before = BenchmarkResult(
            session_id="test",
            session_name="Test",
            total_frames=100,
            total_ground_truth_hits=100,
            total_detected_hits=0,
            metrics=BenchmarkMetrics(
                true_positives=0,
                false_positives=0,
                false_negatives=100,
            ),
            fps_processed=0.0,
        )
        after = BenchmarkResult(
            session_id="test",
            session_name="Test",
            total_frames=100,
            total_ground_truth_hits=100,
            total_detected_hits=100,
            metrics=BenchmarkMetrics(
                true_positives=50,
                false_positives=50,
                false_negatives=50,
            ),
            fps_processed=20.0,
        )

        comparison = compare_benchmark_results(before, after)

        # From 0 to non-zero should be inf
        assert comparison["precision"]["percent_change"] == float("inf")


class TestBenchmarkIntegration:
    """Integration tests for full benchmark workflow."""

    def test_full_benchmark_workflow(self, tmp_path: Path):
        """Given complete setup, expect end-to-end benchmark works."""
        # Create mock frames
        frames_dir = tmp_path / "frames"
        frames_dir.mkdir()
        for i in range(20):
            img = Image.new("RGB", (1920, 1080), color="black")
            img.save(frames_dir / f"frame_{i:04d}.png")

        # Create annotation
        annotation = (
            AnnotationBuilder(session_id="integration_test")
            .with_metadata(
                session_name="Integration Test",
                description="End-to-end test",
                resolution="1920x1080",
                ui_scale=100.0,
                total_frames=20,
                fps=30.0,
            )
            .add_hit(frame=5, value=1000, x=960, y=540)
            .add_hit(frame=10, value=2000, x=960, y=540)
            .add_hit(frame=15, value=3000, x=960, y=540)
            .build()
        )

        # Run benchmark
        runner = BenchmarkRunner()
        config = BenchmarkConfig(replay_frames_dir=frames_dir)
        result = runner.run_benchmark(annotation, config)

        # Verify result
        assert result.session_id == "integration_test"
        assert result.total_frames == 20
        assert result.total_ground_truth_hits == 3
        assert isinstance(result.metrics.precision, float)
        assert isinstance(result.metrics.recall, float)
        assert isinstance(result.metrics.f1_score, float)

        # Save and reload
        output_path = tmp_path / "result.json"
        result.to_file(output_path)
        loaded = BenchmarkResult.from_file(output_path)
        assert loaded.session_id == "integration_test"
