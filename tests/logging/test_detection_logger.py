"""Tests for detection logging functionality."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image

from d4v.logging import (
    AcceptanceEntry,
    AcceptanceReason,
    CandidateInfo,
    DetectionLogger,
    MetricsLogger,
    RejectionEntry,
    RejectionReason,
    SnapshotCapture,
    SnapshotStrategy,
)


class TestCandidateInfo:
    """Tests for CandidateInfo dataclass."""

    def test_create_candidate(self):
        """Given valid parameters, expect candidate created."""
        candidate = CandidateInfo(
            center_x=500.0,
            center_y=300.0,
            width=60,
            height=24,
            raw_text="1234",
            parsed_value=1234,
            confidence=0.85,
            member_count=3,
        )
        assert candidate.center_x == 500.0
        assert candidate.parsed_value == 1234
        assert candidate.confidence == 0.85

    def test_to_dict(self):
        """Given candidate, expect dict with all fields."""
        candidate = CandidateInfo(
            center_x=500.0,
            center_y=300.0,
            width=60,
            height=24,
            raw_text="1234",
            parsed_value=1234,
            confidence=0.85,
            member_count=3,
        )
        result = candidate.to_dict()
        assert result["center_x"] == 500.0
        assert result["raw_text"] == "1234"
        assert result["parsed_value"] == 1234


class TestRejectionEntry:
    """Tests for RejectionEntry."""

    def test_create_rejection_entry(self):
        """Given candidate and reasons, expect rejection entry."""
        candidate = CandidateInfo(
            center_x=500.0,
            center_y=300.0,
            width=60,
            height=24,
            raw_text="abc",
            parsed_value=None,
            confidence=0.4,
            member_count=2,
        )
        entry = RejectionEntry(
            candidate=candidate,
            reasons=[RejectionReason.LOW_CONFIDENCE, RejectionReason.IMPLAUSIBLE_TEXT],
            confidence=0.4,
        )
        assert len(entry.reasons) == 2
        assert entry.confidence == 0.4
        assert not entry.snapshot_available

    def test_to_dict(self):
        """Given rejection entry, expect dict serialization."""
        candidate = CandidateInfo(
            center_x=500.0,
            center_y=300.0,
            width=60,
            height=24,
            raw_text="abc",
            parsed_value=None,
            confidence=0.4,
            member_count=2,
        )
        entry = RejectionEntry(
            candidate=candidate,
            reasons=[RejectionReason.LOW_CONFIDENCE],
            confidence=0.4,
            snapshot_available=True,
        )
        result = entry.to_dict()
        assert result["confidence"] == 0.4
        assert result["snapshot_available"]
        assert len(result["reasons"]) == 1


class TestAcceptanceEntry:
    """Tests for AcceptanceEntry."""

    def test_create_acceptance_entry(self):
        """Given candidate and reasons, expect acceptance entry."""
        candidate = CandidateInfo(
            center_x=500.0,
            center_y=300.0,
            width=60,
            height=24,
            raw_text="1234",
            parsed_value=1234,
            confidence=0.85,
            member_count=3,
        )
        entry = AcceptanceEntry(
            candidate=candidate,
            reasons=[AcceptanceReason.HIGH_CONFIDENCE],
            final_confidence=0.85,
            parsed_value=1234,
        )
        assert entry.final_confidence == 0.85
        assert entry.parsed_value == 1234

    def test_to_dict(self):
        """Given acceptance entry, expect dict serialization."""
        candidate = CandidateInfo(
            center_x=500.0,
            center_y=300.0,
            width=60,
            height=24,
            raw_text="1234",
            parsed_value=1234,
            confidence=0.85,
            member_count=3,
        )
        entry = AcceptanceEntry(
            candidate=candidate,
            reasons=[AcceptanceReason.HIGH_CONFIDENCE],
            final_confidence=0.85,
            parsed_value=1234,
        )
        result = entry.to_dict()
        assert result["final_confidence"] == 0.85
        assert result["parsed_value"] == 1234


class TestDetectionLogger:
    """Tests for DetectionLogger."""

    def test_logger_creation(self, tmp_path: Path):
        """Given logger created, expect directories created."""
        logger = DetectionLogger(
            session_id="test",
            log_dir=tmp_path,
        )
        assert logger.log_dir.exists()
        assert logger.snapshot_dir.exists()

    def test_logger_log_frame(self, tmp_path: Path):
        """Given frame logged, expect entry created."""
        logger = DetectionLogger(
            session_id="test",
            log_dir=tmp_path,
        )

        candidate = CandidateInfo(
            center_x=500.0,
            center_y=300.0,
            width=60,
            height=24,
            raw_text="1234",
            parsed_value=1234,
            confidence=0.85,
            member_count=3,
        )

        accepted = logger.create_acceptance_entry(
            candidate=candidate,
            reasons=[AcceptanceReason.HIGH_CONFIDENCE],
            final_confidence=0.85,
            parsed_value=1234,
        )

        entry = logger.log_frame(
            frame_index=100,
            timestamp_ms=3333,
            candidates=[candidate],
            accepted=[accepted],
            rejected=[],
            processing_time_ms=45.2,
        )

        assert entry.frame_index == 100
        assert entry.hits_accepted == 1
        assert logger.total_candidates == 1
        assert logger.total_accepted == 1

    def test_logger_rejection_tracking(self, tmp_path: Path):
        """Given rejections logged, expect reasons tracked."""
        logger = DetectionLogger(
            session_id="test",
            log_dir=tmp_path,
        )

        candidate = CandidateInfo(
            center_x=500.0,
            center_y=300.0,
            width=60,
            height=24,
            raw_text="abc",
            parsed_value=None,
            confidence=0.4,
            member_count=2,
        )

        rejected = logger.create_rejection_entry(
            candidate=candidate,
            reasons=[RejectionReason.LOW_CONFIDENCE],
        )

        logger.log_frame(
            frame_index=100,
            timestamp_ms=3333,
            candidates=[candidate],
            accepted=[],
            rejected=[rejected],
            processing_time_ms=45.2,
        )

        assert logger.total_rejected == 1
        assert RejectionReason.LOW_CONFIDENCE in logger.rejection_reason_counts

    def test_logger_get_summary(self, tmp_path: Path):
        """Given session logged, expect summary statistics."""
        logger = DetectionLogger(
            session_id="test",
            log_dir=tmp_path,
        )

        candidate = CandidateInfo(
            center_x=500.0,
            center_y=300.0,
            width=60,
            height=24,
            raw_text="1234",
            parsed_value=1234,
            confidence=0.85,
            member_count=3,
        )

        accepted = logger.create_acceptance_entry(
            candidate=candidate,
            reasons=[AcceptanceReason.HIGH_CONFIDENCE],
            final_confidence=0.85,
            parsed_value=1234,
        )

        logger.log_frame(
            frame_index=100,
            timestamp_ms=3333,
            candidates=[candidate],
            accepted=[accepted],
            rejected=[],
            processing_time_ms=45.2,
        )

        summary = logger.get_session_summary()

        assert summary["session_id"] == "test"
        assert summary["total_frames"] == 1
        assert summary["acceptance_rate"] == 1.0

    def test_logger_export_summary(self, tmp_path: Path):
        """Given summary exported, expect JSON file created."""
        logger = DetectionLogger(
            session_id="test",
            log_dir=tmp_path,
        )

        output_path = tmp_path / "summary.json"
        logger.export_summary(output_path)

        assert output_path.exists()
        with open(output_path) as f:
            data = json.load(f)
        assert data["session_id"] == "test"


class TestSnapshotCapture:
    """Tests for SnapshotCapture."""

    def test_capture_creation(self, tmp_path: Path):
        """Given capture created, expect directory created."""
        capture = SnapshotCapture(
            session_id="test",
            snapshot_dir=tmp_path,
        )
        assert capture.snapshot_dir.exists()

    def test_capture_snapshot(self, tmp_path: Path):
        """Given image captured, expect file saved."""
        capture = SnapshotCapture(
            session_id="test",
            snapshot_dir=tmp_path,
            max_snapshots=10,
        )

        # Create test image
        image = Image.new("RGB", (1920, 1080), color="black")

        metadata = capture.capture(
            image=image,
            frame_index=100,
            reason="test",
            candidate_count=5,
            accepted_count=2,
            rejected_count=3,
            processing_time_ms=45.2,
        )

        assert metadata is not None
        assert Path(metadata.snapshot_path).exists()

    def test_capture_rejection_helper(self, tmp_path: Path):
        """Given rejection capture, expect file saved with metadata."""
        capture = SnapshotCapture(
            session_id="test",
            snapshot_dir=tmp_path,
        )

        image = Image.new("RGB", (1920, 1080), color="black")

        metadata = capture.capture_rejection(
            image=image,
            frame_index=100,
            rejected_candidates=[{"value": 1234}],
            processing_time_ms=45.2,
        )

        assert metadata is not None
        assert metadata.reason == "rejection"

    def test_capture_acceptance_helper(self, tmp_path: Path):
        """Given acceptance capture, expect file saved with metadata."""
        capture = SnapshotCapture(
            session_id="test",
            snapshot_dir=tmp_path,
        )

        image = Image.new("RGB", (1920, 1080), color="black")

        metadata = capture.capture_acceptance(
            image=image,
            frame_index=100,
            accepted_candidates=[{"value": 1234}],
            processing_time_ms=45.2,
        )

        assert metadata is not None
        assert metadata.reason == "acceptance"

    def test_max_snapshots_limit(self, tmp_path: Path):
        """Given max snapshots reached, expect no new captures."""
        capture = SnapshotCapture(
            session_id="test",
            snapshot_dir=tmp_path,
            max_snapshots=2,
        )

        image = Image.new("RGB", (100, 100), color="black")

        # Capture 2 snapshots
        result1 = capture.capture(
            image=image, frame_index=1, reason="test",
            candidate_count=0, accepted_count=0, rejected_count=0,
            processing_time_ms=1.0,
        )
        result2 = capture.capture(
            image=image, frame_index=2, reason="test",
            candidate_count=0, accepted_count=0, rejected_count=0,
            processing_time_ms=1.0,
        )

        # Third should be None (max reached)
        result3 = capture.capture(
            image=image, frame_index=3, reason="test",
            candidate_count=0, accepted_count=0, rejected_count=0,
            processing_time_ms=1.0,
        )

        assert result1 is not None
        assert result2 is not None
        assert result3 is None

    def test_snapshot_index(self, tmp_path: Path):
        """Given snapshots captured, expect index available."""
        capture = SnapshotCapture(
            session_id="test",
            snapshot_dir=tmp_path,
        )

        image = Image.new("RGB", (100, 100), color="black")

        capture.capture(
            image=image, frame_index=1, reason="test",
            candidate_count=0, accepted_count=0, rejected_count=0,
            processing_time_ms=1.0,
        )

        index = capture.get_snapshot_index()
        assert len(index) == 1

    def test_statistics(self, tmp_path: Path):
        """Given snapshots captured, expect statistics available."""
        capture = SnapshotCapture(
            session_id="test",
            snapshot_dir=tmp_path,
        )

        image = Image.new("RGB", (100, 100), color="black")

        capture.capture(
            image=image, frame_index=1, reason="rejection",
            candidate_count=5, accepted_count=0, rejected_count=5,
            processing_time_ms=1.0,
        )
        capture.capture(
            image=image, frame_index=2, reason="acceptance",
            candidate_count=2, accepted_count=2, rejected_count=0,
            processing_time_ms=1.0,
        )

        stats = capture.get_statistics()
        assert stats["total_snapshots"] == 2
        assert "rejection" in stats["by_reason"]
        assert "acceptance" in stats["by_reason"]


class TestSnapshotStrategy:
    """Tests for SnapshotStrategy."""

    def test_strategy_default_config(self):
        """Given default strategy, expect rejection capture enabled."""
        strategy = SnapshotStrategy()
        assert strategy.capture_on_rejection
        assert strategy.capture_on_low_confidence

    def test_should_capture_on_rejection(self):
        """Given rejection, expect capture triggered."""
        strategy = SnapshotStrategy(capture_on_rejection=True)
        should_capture, reason = strategy.should_capture(
            frame_index=100,
            accepted_count=0,
            rejected_count=5,
            max_confidence=0.5,
        )
        assert should_capture
        assert reason == "rejection"

    def test_should_capture_on_low_confidence(self):
        """Given low confidence, expect capture triggered."""
        strategy = SnapshotStrategy(
            capture_on_low_confidence=True,
            low_confidence_threshold=0.65,
        )
        should_capture, reason = strategy.should_capture(
            frame_index=100,
            accepted_count=1,
            rejected_count=0,
            max_confidence=0.5,
        )
        assert should_capture
        assert reason == "low_confidence"

    def test_should_capture_periodic(self):
        """Given periodic frame, expect capture triggered."""
        strategy = SnapshotStrategy(capture_every_n_frames=10)
        should_capture, reason = strategy.should_capture(
            frame_index=100,
            accepted_count=0,
            rejected_count=0,
            max_confidence=0.0,
        )
        assert should_capture
        assert reason == "periodic"

    def test_should_not_capture(self):
        """Given no trigger conditions, expect no capture."""
        strategy = SnapshotStrategy(
            capture_on_rejection=False,
            capture_on_acceptance=False,
            capture_on_low_confidence=False,
            capture_every_n_frames=0,
        )
        should_capture, reason = strategy.should_capture(
            frame_index=100,
            accepted_count=1,
            rejected_count=0,
            max_confidence=0.8,
        )
        assert not should_capture


class TestMetricsLogger:
    """Tests for MetricsLogger."""

    def test_metrics_logger_creation(self):
        """Given logger created, expect initialized."""
        logger = MetricsLogger(session_id="test")
        assert logger.session_id == "test"
        assert logger.total_frames == 0

    def test_log_frame(self):
        """Given frame logged, expect accumulators updated."""
        logger = MetricsLogger(session_id="test")

        logger.log_frame(
            frame_index=100,
            candidates=5,
            hits=2,
            rejected=3,
            damage_values=[1234, 5678],
            confidences=[0.85, 0.92],
            processing_time_ms=45.2,
        )

        assert logger.total_frames == 1
        assert logger.total_candidates == 5
        assert logger.total_hits == 2
        assert logger.total_rejected == 3
        assert logger.total_damage == 1234 + 5678
        assert logger.biggest_hit == 5678

    def test_log_multiple_frames(self):
        """Given multiple frames logged, expect aggregation."""
        logger = MetricsLogger(session_id="test")

        for i in range(10):
            logger.log_frame(
                frame_index=i,
                candidates=5,
                hits=2,
                rejected=3,
                damage_values=[1000],
                confidences=[0.8],
                processing_time_ms=40.0,
            )

        assert logger.total_frames == 10
        assert logger.total_damage == 10000
        assert logger.biggest_hit == 1000

    def test_get_metrics(self):
        """Given metrics requested, expect aggregated statistics."""
        logger = MetricsLogger(session_id="test")

        logger.log_frame(
            frame_index=0,
            candidates=10,
            hits=3,  # Match number of confidence values
            rejected=7,
            damage_values=[1000, 2000, 3000],
            confidences=[0.8, 0.9, 0.85],
            processing_time_ms=45.0,
        )

        metrics = logger.get_metrics()

        assert metrics.total_frames == 1
        assert metrics.total_damage == 6000
        assert metrics.biggest_hit == 3000
        # Average of 0.8, 0.9, 0.85 = 0.85
        assert abs(metrics.avg_confidence - 0.85) < 0.01

    def test_acceptance_rate(self):
        """Given hits and candidates, expect acceptance rate calculated."""
        logger = MetricsLogger(session_id="test")

        logger.log_frame(
            frame_index=0,
            candidates=10,
            hits=7,
            rejected=3,
        )

        metrics = logger.get_metrics()
        assert abs(metrics.acceptance_rate - 0.7) < 0.01

    def test_damage_bucketing(self):
        """Given damage values, expect correct bucketing."""
        logger = MetricsLogger(session_id="test")

        logger.log_frame(
            frame_index=0,
            candidates=5,
            hits=5,
            rejected=0,
            damage_values=[500, 5000, 50000, 500000, 5000000],
            confidences=[0.8] * 5,
        )

        metrics = logger.get_metrics()
        assert metrics.damage_distribution["0-1k"] == 1
        assert metrics.damage_distribution["1k-10k"] == 1
        assert metrics.damage_distribution["10k-100k"] == 1
        assert metrics.damage_distribution["100k-1M"] == 1
        assert metrics.damage_distribution["1M+"] == 1

    def test_confidence_bucketing(self):
        """Given confidence values, expect correct bucketing."""
        logger = MetricsLogger(session_id="test")

        logger.log_frame(
            frame_index=0,
            candidates=5,
            hits=5,
            rejected=0,
            damage_values=[1000] * 5,
            confidences=[0.1, 0.3, 0.5, 0.7, 0.9],
        )

        metrics = logger.get_metrics()
        assert metrics.confidence_distribution["0.0-0.2"] == 1
        assert metrics.confidence_distribution["0.2-0.4"] == 1
        assert metrics.confidence_distribution["0.4-0.6"] == 1
        assert metrics.confidence_distribution["0.6-0.8"] == 1
        assert metrics.confidence_distribution["0.8-1.0"] == 1

    def test_export_report(self, tmp_path: Path):
        """Given report exported, expect JSON file created."""
        logger = MetricsLogger(session_id="test")

        logger.log_frame(
            frame_index=0,
            candidates=5,
            hits=2,
            rejected=3,
            damage_values=[1234],
            confidences=[0.85],
        )

        output_path = tmp_path / "metrics.json"
        logger.export_report(output_path)

        assert output_path.exists()
        with open(output_path) as f:
            data = json.load(f)
        assert data["session_id"] == "test"
        assert data["total_damage"] == 1234

    def test_frame_rate_analysis(self):
        """Given frames logged, expect frame rate analysis available."""
        logger = MetricsLogger(session_id="test")

        for i in range(5):
            logger.log_frame(
                frame_index=i,
                candidates=1,
                hits=1,
                rejected=0,
            )

        analysis = logger.get_frame_rate_analysis()
        assert analysis["total_frames"] == 5
        assert "avg_fps" in analysis
