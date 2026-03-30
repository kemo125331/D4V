"""Tests for benchmark metrics calculation."""

import pytest

from d4v.benchmark.metrics import (
    BenchmarkMetrics,
    compute_metrics,
    compute_per_frame_metrics,
    compute_value_range_metrics,
    match_detections_to_ground_truth,
)


class TestBenchmarkMetrics:
    """Tests for BenchmarkMetrics dataclass."""

    def test_perfect_precision_recall(self):
        """Given perfect detection, expect precision=1.0, recall=1.0."""
        metrics = BenchmarkMetrics(
            true_positives=100,
            false_positives=0,
            false_negatives=0,
        )
        assert metrics.precision == 1.0
        assert metrics.recall == 1.0
        assert metrics.f1_score == 1.0

    def test_precision_calculation(self):
        """Given 85 TP and 15 FP, expect precision = 0.85."""
        metrics = BenchmarkMetrics(
            true_positives=85,
            false_positives=15,
            false_negatives=0,
        )
        assert metrics.precision == 0.85

    def test_recall_calculation(self):
        """Given 90 TP and 10 FN, expect recall = 0.90."""
        metrics = BenchmarkMetrics(
            true_positives=90,
            false_positives=0,
            false_negatives=10,
        )
        assert metrics.recall == 0.9

    def test_f1_score_calculation(self):
        """Given 85 TP, 15 FP, 10 FN, expect F1 ≈ 0.872."""
        metrics = BenchmarkMetrics(
            true_positives=85,
            false_positives=15,
            false_negatives=10,
        )
        # Precision = 85/(85+15) = 0.85
        # Recall = 85/(85+10) = 0.8947...
        # F1 = 2 * (0.85 * 0.8947) / (0.85 + 0.8947) ≈ 0.872
        assert abs(metrics.f1_score - 0.872) < 0.003

    def test_zero_division_precision(self):
        """Given no detections, expect precision = 0.0 (not exception)."""
        metrics = BenchmarkMetrics(
            true_positives=0,
            false_positives=0,
            false_negatives=100,
        )
        assert metrics.precision == 0.0

    def test_zero_division_recall(self):
        """Given no ground truth, expect recall = 0.0 (not exception)."""
        metrics = BenchmarkMetrics(
            true_positives=0,
            false_positives=100,
            false_negatives=0,
        )
        assert metrics.recall == 0.0

    def test_zero_division_f1(self):
        """Given P=0 and R=0, expect F1 = 0.0 (not exception)."""
        metrics = BenchmarkMetrics(
            true_positives=0,
            false_positives=0,
            false_negatives=0,
        )
        assert metrics.f1_score == 0.0

    def test_to_dict(self):
        """Given metrics, expect dict with rounded values."""
        metrics = BenchmarkMetrics(
            true_positives=85,
            false_positives=15,
            false_negatives=10,
        )
        result = metrics.to_dict()
        assert result["true_positives"] == 85
        assert result["false_positives"] == 15
        assert result["false_negatives"] == 10
        assert result["precision"] == 0.85
        assert abs(result["recall"] - 0.8947) < 0.001
        assert abs(result["f1_score"] - 0.872) < 0.003


class TestMatchDetectionsToGroundTruth:
    """Tests for detection matching algorithm."""

    def test_perfect_match(self):
        """Given identical detection and GT, expect TP match."""
        detections = [
            {"frame": 10, "value": 1000, "center_x": 500, "center_y": 300},
        ]
        ground_truth = [
            {"frame": 10, "value": 1000, "x": 500, "y": 300},
        ]
        result = match_detections_to_ground_truth(detections, ground_truth)
        assert len(result["true_positives"]) == 1
        assert len(result["false_positives"]) == 0
        assert len(result["false_negatives"]) == 0

    def test_within_tolerance_match(self):
        """Given detection within tolerances, expect TP match."""
        detections = [
            {"frame": 10, "value": 1050, "center_x": 510, "center_y": 305},
        ]
        ground_truth = [
            {"frame": 10, "value": 1000, "x": 500, "y": 300},
        ]
        result = match_detections_to_ground_truth(
            detections,
            ground_truth,
            frame_tolerance=3,
            value_tolerance=0.1,  # 10%
            spatial_tolerance=70.0,
        )
        assert len(result["true_positives"]) == 1

    def test_value_outside_tolerance(self):
        """Given value outside tolerance, expect FP and FN."""
        detections = [
            {"frame": 10, "value": 2000, "center_x": 500, "center_y": 300},
        ]
        ground_truth = [
            {"frame": 10, "value": 1000, "x": 500, "y": 300},
        ]
        result = match_detections_to_ground_truth(
            detections,
            ground_truth,
            value_tolerance=0.1,  # 10% tolerance, 2000 is 100% off
        )
        assert len(result["true_positives"]) == 0
        assert len(result["false_positives"]) == 1
        assert len(result["false_negatives"]) == 1

    def test_spatial_outside_tolerance(self):
        """Given position outside tolerance, expect FP and FN."""
        detections = [
            {"frame": 10, "value": 1000, "center_x": 700, "center_y": 500},
        ]
        ground_truth = [
            {"frame": 10, "value": 1000, "x": 500, "y": 300},
        ]
        result = match_detections_to_ground_truth(
            detections,
            ground_truth,
            spatial_tolerance=70.0,  # Distance is ~283px
        )
        assert len(result["true_positives"]) == 0
        assert len(result["false_positives"]) == 1
        assert len(result["false_negatives"]) == 1

    def test_frame_outside_tolerance(self):
        """Given frame outside tolerance, expect no match."""
        detections = [
            {"frame": 20, "value": 1000, "center_x": 500, "center_y": 300},
        ]
        ground_truth = [
            {"frame": 10, "value": 1000, "x": 500, "y": 300},
        ]
        result = match_detections_to_ground_truth(
            detections,
            ground_truth,
            frame_tolerance=3,  # Difference is 10 frames
        )
        assert len(result["true_positives"]) == 0
        assert len(result["false_positives"]) == 1
        assert len(result["false_negatives"]) == 1

    def test_multiple_detections_one_ground_truth(self):
        """Given 2 detections for 1 GT, expect 1 TP and 1 FP."""
        detections = [
            {"frame": 10, "value": 1000, "center_x": 500, "center_y": 300},
            {"frame": 10, "value": 1000, "center_x": 510, "center_y": 305},
        ]
        ground_truth = [
            {"frame": 10, "value": 1000, "x": 500, "y": 300},
        ]
        result = match_detections_to_ground_truth(detections, ground_truth)
        assert len(result["true_positives"]) == 1
        assert len(result["false_positives"]) == 1
        assert len(result["false_negatives"]) == 0

    def test_one_detection_multiple_ground_truth(self):
        """Given 1 detection for 2 GT, expect 1 TP and 1 FN."""
        detections = [
            {"frame": 10, "value": 1000, "center_x": 500, "center_y": 300},
        ]
        ground_truth = [
            {"frame": 10, "value": 1000, "x": 500, "y": 300},
            {"frame": 10, "value": 2000, "x": 600, "y": 400},
        ]
        result = match_detections_to_ground_truth(detections, ground_truth)
        assert len(result["true_positives"]) == 1
        assert len(result["false_positives"]) == 0
        assert len(result["false_negatives"]) == 1

    def test_best_spatial_match(self):
        """Given 2 GT and 1 detection, match closest spatially."""
        detections = [
            {"frame": 10, "value": 1000, "center_x": 505, "center_y": 305},
        ]
        ground_truth = [
            {"frame": 10, "value": 1000, "x": 500, "y": 300},  # Close (7px)
            {"frame": 10, "value": 1000, "x": 600, "y": 400},  # Far (134px)
        ]
        result = match_detections_to_ground_truth(detections, ground_truth)
        assert len(result["true_positives"]) == 1
        assert result["true_positives"][0][1] == 0  # Matched first GT


class TestComputeMetrics:
    """Tests for high-level metrics computation."""

    def test_compute_metrics_basic(self):
        """Given simple detections and GT, expect correct metrics."""
        detections = [
            {"frame": 10, "value": 1000, "center_x": 500, "center_y": 300},
            {"frame": 20, "value": 2000, "center_x": 600, "center_y": 400},
            {"frame": 30, "value": 3000, "center_x": 700, "center_y": 500},  # FP
        ]
        ground_truth = [
            {"frame": 10, "value": 1000, "x": 500, "y": 300},
            {"frame": 20, "value": 2000, "x": 600, "y": 400},
            {"frame": 40, "value": 4000, "x": 800, "y": 600},  # FN
        ]
        metrics = compute_metrics(detections, ground_truth)
        assert metrics.true_positives == 2
        assert metrics.false_positives == 1
        assert metrics.false_negatives == 1
        assert metrics.precision == 2 / 3  # 0.667
        assert metrics.recall == 2 / 3  # 0.667

    def test_empty_detections(self):
        """Given no detections, expect precision=0, recall=0."""
        detections = []
        ground_truth = [
            {"frame": 10, "value": 1000, "x": 500, "y": 300},
        ]
        metrics = compute_metrics(detections, ground_truth)
        assert metrics.precision == 0.0
        assert metrics.recall == 0.0
        assert metrics.false_negatives == 1

    def test_empty_ground_truth(self):
        """Given no ground truth, expect precision=0, recall=0."""
        detections = [
            {"frame": 10, "value": 1000, "center_x": 500, "center_y": 300},
        ]
        ground_truth = []
        metrics = compute_metrics(detections, ground_truth)
        assert metrics.precision == 0.0
        assert metrics.recall == 0.0
        assert metrics.false_positives == 1


class TestComputePerFrameMetrics:
    """Tests for per-frame metrics computation."""

    def test_per_frame_breakdown(self):
        """Given detections across frames, expect metrics per frame."""
        detections = [
            {"frame": 10, "value": 1000, "center_x": 500, "center_y": 300},
            {"frame": 10, "value": 1500, "center_x": 550, "center_y": 350},
            {"frame": 20, "value": 2000, "center_x": 600, "center_y": 400},
        ]
        ground_truth = [
            {"frame": 10, "value": 1000, "x": 500, "y": 300},
            {"frame": 20, "value": 2000, "x": 600, "y": 400},
        ]
        per_frame = compute_per_frame_metrics(detections, ground_truth)
        assert 10 in per_frame
        assert 20 in per_frame
        # Frame 10: 1 TP, 1 FP
        assert per_frame[10].true_positives == 1
        assert per_frame[10].false_positives == 1
        # Frame 20: 1 TP, 0 FP
        assert per_frame[20].true_positives == 1
        assert per_frame[20].false_positives == 0


class TestComputeValueRangeMetrics:
    """Tests for value range breakdown."""

    def test_range_breakdown(self):
        """Given different value ranges, expect separate metrics."""
        detections = [
            {"frame": 10, "value": 500, "center_x": 500, "center_y": 300},
            {"frame": 20, "value": 5000, "center_x": 600, "center_y": 400},
            {"frame": 30, "value": 50000, "center_x": 700, "center_y": 500},
        ]
        ground_truth = [
            {"frame": 10, "value": 500, "x": 500, "y": 300},
            {"frame": 20, "value": 5000, "x": 600, "y": 400},
            {"frame": 30, "value": 50000, "x": 700, "y": 500},
        ]
        value_ranges = [
            (None, 1000, "tiny"),
            (1000, 10000, "small"),
            (10000, None, "medium"),
        ]
        range_metrics = compute_value_range_metrics(
            detections, ground_truth, value_ranges=value_ranges
        )
        assert "tiny" in range_metrics
        assert "small" in range_metrics
        assert "medium" in range_metrics
        assert range_metrics["tiny"].true_positives == 1
        assert range_metrics["small"].true_positives == 1
        assert range_metrics["medium"].true_positives == 1
