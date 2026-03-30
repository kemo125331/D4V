"""Benchmark metrics calculation for detection evaluation.

Computes precision, recall, F1 score, and other detection metrics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict


@dataclass(frozen=True)
class BenchmarkMetrics:
    """Detection performance metrics.

    Attributes:
        true_positives: Correctly detected hits.
        false_positives: Incorrectly detected hits (false alarms).
        false_negatives: Missed hits (ground truth not detected).
        true_negatives: Correctly rejected non-hit regions (rarely used).
        precision: TP / (TP + FP) - How many detections were correct.
        recall: TP / (TP + FN) - How many ground truth hits were found.
        f1_score: Harmonic mean of precision and recall.
        accuracy: (TP + TN) / Total - Overall correctness.
    """

    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int = 0

    @property
    def precision(self) -> float:
        """Calculate precision: TP / (TP + FP)."""
        denominator = self.true_positives + self.false_positives
        if denominator == 0:
            return 0.0
        return self.true_positives / denominator

    @property
    def recall(self) -> float:
        """Calculate recall: TP / (TP + FN)."""
        denominator = self.true_positives + self.false_negatives
        if denominator == 0:
            return 0.0
        return self.true_positives / denominator

    @property
    def f1_score(self) -> float:
        """Calculate F1 score: harmonic mean of precision and recall."""
        if self.precision + self.recall == 0:
            return 0.0
        return 2 * (self.precision * self.recall) / (self.precision + self.recall)

    @property
    def accuracy(self) -> float:
        """Calculate accuracy: (TP + TN) / Total."""
        total = self.true_positives + self.false_positives + self.false_negatives + self.true_negatives
        if total == 0:
            return 0.0
        return (self.true_positives + self.true_negatives) / total

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "true_negatives": self.true_negatives,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1_score": round(self.f1_score, 4),
            "accuracy": round(self.accuracy, 4),
        }


class MatchResult(TypedDict):
    """Result of matching detections to ground truth."""

    true_positives: list[tuple[int, int]]  # List of (detection_id, ground_truth_id) pairs
    false_positives: list[int]  # List of detection IDs with no match
    false_negatives: list[int]  # List of ground truth IDs with no match


def match_detections_to_ground_truth(
    detections: list[dict],
    ground_truth: list[dict],
    frame_tolerance: int = 3,
    value_tolerance: float = 0.1,
    spatial_tolerance: float = 70.0,
) -> MatchResult:
    """Match detected hits to ground truth annotations.

    A detection matches ground truth if:
    - Frame index is within tolerance
    - Damage value is within percentage tolerance
    - Spatial position is within pixel distance

    Args:
        detections: List of detected hits with frame, value, center_x, center_y.
        ground_truth: List of ground truth hits with frame, value, x, y.
        frame_tolerance: Maximum frame difference for a match.
        value_tolerance: Maximum value difference as fraction (0.1 = 10%).
        spatial_tolerance: Maximum pixel distance for a match.

    Returns:
        MatchResult with TP, FP, FN classifications.
    """
    matched_detections: set[int] = set()
    matched_ground_truth: set[int] = set()
    true_positives: list[tuple[int, int]] = []

    for det_idx, detection in enumerate(detections):
        best_match_idx: int | None = None
        best_match_distance: float = float("inf")

        for gt_idx, gt in enumerate(ground_truth):
            if gt_idx in matched_ground_truth:
                continue

            # Check frame tolerance
            frame_diff = abs(detection.get("frame", 0) - gt.get("frame", 0))
            if frame_diff > frame_tolerance:
                continue

            # Check value tolerance
            det_value = detection.get("value", 0)
            gt_value = gt.get("value", 0)
            if gt_value == 0:
                value_diff = float("inf") if det_value != 0 else 0.0
            else:
                value_diff = abs(det_value - gt_value) / gt_value
            if value_diff > value_tolerance:
                continue

            # Check spatial tolerance
            det_x = detection.get("center_x", 0)
            det_y = detection.get("center_y", 0)
            gt_x = gt.get("x", 0)
            gt_y = gt.get("y", 0)
            spatial_distance = ((det_x - gt_x) ** 2 + (det_y - gt_y) ** 2) ** 0.5

            if spatial_distance > spatial_tolerance:
                continue

            # Find best match (closest spatially)
            if spatial_distance < best_match_distance:
                best_match_distance = spatial_distance
                best_match_idx = gt_idx

        if best_match_idx is not None:
            matched_detections.add(det_idx)
            matched_ground_truth.add(best_match_idx)
            true_positives.append((det_idx, best_match_idx))

    false_positives = [i for i in range(len(detections)) if i not in matched_detections]
    false_negatives = [i for i in range(len(ground_truth)) if i not in matched_ground_truth]

    return MatchResult(
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives,
    )


def compute_metrics(
    detections: list[dict],
    ground_truth: list[dict],
    frame_tolerance: int = 3,
    value_tolerance: float = 0.1,
    spatial_tolerance: float = 70.0,
) -> BenchmarkMetrics:
    """Compute benchmark metrics for detection results.

    Args:
        detections: List of detected hits.
        ground_truth: List of ground truth annotations.
        frame_tolerance: Maximum frame difference for matching.
        value_tolerance: Maximum value difference as fraction.
        spatial_tolerance: Maximum pixel distance for matching.

    Returns:
        BenchmarkMetrics with precision, recall, F1, accuracy.
    """
    match_result = match_detections_to_ground_truth(
        detections=detections,
        ground_truth=ground_truth,
        frame_tolerance=frame_tolerance,
        value_tolerance=value_tolerance,
        spatial_tolerance=spatial_tolerance,
    )

    return BenchmarkMetrics(
        true_positives=len(match_result["true_positives"]),
        false_positives=len(match_result["false_positives"]),
        false_negatives=len(match_result["false_negatives"]),
        true_negatives=0,  # True negatives not meaningful for detection tasks
    )


def compute_per_frame_metrics(
    detections: list[dict],
    ground_truth: list[dict],
    frame_tolerance: int = 3,
    value_tolerance: float = 0.1,
    spatial_tolerance: float = 70.0,
) -> dict[int, BenchmarkMetrics]:
    """Compute metrics broken down by frame index.

    Useful for identifying problematic frames or time periods.

    Args:
        detections: List of detected hits.
        ground_truth: List of ground truth annotations.
        frame_tolerance: Maximum frame difference for matching.
        value_tolerance: Maximum value difference as fraction.
        spatial_tolerance: Maximum pixel distance for matching.

    Returns:
        Dictionary mapping frame index to BenchmarkMetrics.
    """
    # Group by frame
    detections_by_frame: dict[int, list[dict]] = {}
    ground_truth_by_frame: dict[int, list[dict]] = {}

    for det in detections:
        frame = det.get("frame", 0)
        detections_by_frame.setdefault(frame, []).append(det)

    for gt in ground_truth:
        frame = gt.get("frame", 0)
        ground_truth_by_frame.setdefault(frame, []).append(gt)

    all_frames = sorted(set(detections_by_frame.keys()) | set(ground_truth_by_frame.keys()))

    per_frame_metrics: dict[int, BenchmarkMetrics] = {}
    for frame in all_frames:
        frame_detections = detections_by_frame.get(frame, [])
        frame_ground_truth = ground_truth_by_frame.get(frame, [])

        per_frame_metrics[frame] = compute_metrics(
            detections=frame_detections,
            ground_truth=frame_ground_truth,
            frame_tolerance=frame_tolerance,
            value_tolerance=value_tolerance,
            spatial_tolerance=spatial_tolerance,
        )

    return per_frame_metrics


def compute_value_range_metrics(
    detections: list[dict],
    ground_truth: list[dict],
    value_ranges: list[tuple[int | None, int | None]] = None,
    **match_kwargs,
) -> dict[str, BenchmarkMetrics]:
    """Compute metrics broken down by damage value ranges.

    Useful for identifying if detection performs differently on small vs large hits.

    Args:
        detections: List of detected hits.
        ground_truth: List of ground truth annotations.
        value_ranges: List of (min_value, max_value) tuples. None means unbounded.
        **match_kwargs: Passed to compute_metrics.

    Returns:
        Dictionary mapping range label to BenchmarkMetrics.
    """
    if value_ranges is None:
        value_ranges = [
            (None, 1000, "tiny (<1k)"),
            (1000, 10000, "small (1k-10k)"),
            (10000, 100000, "medium (10k-100k)"),
            (100000, 1000000, "large (100k-1M)"),
            (1000000, None, "huge (>1M)"),
        ]

    range_metrics: dict[str, BenchmarkMetrics] = {}

    for min_val, max_val, label in value_ranges:
        # Filter ground truth to range
        filtered_gt = []
        for gt in ground_truth:
            value = gt.get("value", 0)
            if min_val is not None and value < min_val:
                continue
            if max_val is not None and value >= max_val:
                continue
            filtered_gt.append(gt)

        # Filter detections that match filtered ground truth
        # (simplified: just use all detections for now)
        range_metrics[label] = compute_metrics(
            detections=detections,
            ground_truth=filtered_gt,
            **match_kwargs,
        )

    return range_metrics
