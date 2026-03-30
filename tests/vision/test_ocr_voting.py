"""Tests for multi-frame OCR voting."""

import sys
from pathlib import Path

import pytest

# Import directly from module file to avoid cv2 dependency in vision/__init__.py
# Add src to path
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

# Import the module directly without going through package __init__
import importlib.util
spec = importlib.util.spec_from_file_location(
    "d4v.vision.ocr_voting",
    src_path / "d4v" / "vision" / "ocr_voting.py"
)
ocr_voting = importlib.util.module_from_spec(spec)
sys.modules["d4v.vision.ocr_voting"] = ocr_voting
spec.loader.exec_module(ocr_voting)

OcrVote = ocr_voting.OcrVote
OcrVoteAggregator = ocr_voting.OcrVoteAggregator
OcrVoteResult = ocr_voting.OcrVoteResult
TrackedDamage = ocr_voting.TrackedDamage
aggregate_ocr_results = ocr_voting.aggregate_ocr_results


class TestOcrVote:
    """Tests for OcrVote dataclass."""

    def test_create_vote(self):
        """Given valid parameters, expect vote created."""
        vote = OcrVote(
            frame_index=10,
            parsed_value=1234,
            confidence=0.85,
            center_x=500.0,
            center_y=300.0,
        )
        assert vote.frame_index == 10
        assert vote.parsed_value == 1234
        assert vote.confidence == 0.85

    def test_to_dict(self):
        """Given vote, expect dict conversion."""
        vote = OcrVote(
            frame_index=10,
            parsed_value=1234,
            confidence=0.85,
            center_x=500.0,
            center_y=300.0,
            raw_text="1234",
            width=80,
            height=24,
        )
        data = vote.to_dict()
        assert data["frame_index"] == 10
        assert data["parsed_value"] == 1234
        assert data["raw_text"] == "1234"


class TestOcrVoteResult:
    """Tests for OcrVoteResult dataclass."""

    def test_create_result(self):
        """Given valid parameters, expect result created."""
        result = OcrVoteResult(
            final_value=1234,
            confidence=0.90,
            vote_count=3,
            total_votes=4,
            agreement_ratio=0.75,
            values_seen=[1234, 1235],
            frames=[10, 11, 12],
            method="weighted_voting",
        )
        assert result.final_value == 1234
        assert result.agreement_ratio == 0.75

    def test_to_dict(self):
        """Given result, expect dict conversion."""
        result = OcrVoteResult(
            final_value=1234,
            confidence=0.90,
            vote_count=3,
            total_votes=4,
            agreement_ratio=0.75,
            values_seen=[1234],
            frames=[10, 11],
            method="majority_voting",
        )
        data = result.to_dict()
        assert data["final_value"] == 1234
        assert data["method"] == "majority_voting"


class TestTrackedDamage:
    """Tests for TrackedDamage."""

    def test_create_track(self):
        """Given track created, expect initialized."""
        track = TrackedDamage(track_id=1)
        assert track.track_id == 1
        assert len(track.votes) == 0
        assert track.velocity_y == 0.0

    def test_add_vote(self):
        """Given vote added, expect track updated."""
        track = TrackedDamage(track_id=1)

        vote = OcrVote(
            frame_index=10,
            parsed_value=1234,
            confidence=0.85,
            center_x=500.0,
            center_y=300.0,
        )
        track.add_vote(vote)

        assert len(track.votes) == 1
        assert track.first_frame == 10
        assert track.last_frame == 10

    def test_add_multiple_votes(self):
        """Given multiple votes, expect frames tracked."""
        track = TrackedDamage(track_id=1)

        for i in range(5):
            vote = OcrVote(
                frame_index=10 + i,
                parsed_value=1234,
                confidence=0.85,
                center_x=500.0,
                center_y=300.0 - i * 2,  # Moving upward
            )
            track.add_vote(vote)

        assert len(track.votes) == 5
        assert track.first_frame == 10
        assert track.last_frame == 14
        assert track.velocity_y < 0  # Moving upward

    def test_velocity_calculation(self):
        """Given votes with movement, expect velocity calculated."""
        track = TrackedDamage(track_id=1)

        # Add votes with consistent upward movement
        for i in range(4):
            vote = OcrVote(
                frame_index=i,
                parsed_value=1234,
                confidence=0.85,
                center_x=500.0,
                center_y=400.0 - i * 10,  # 10 pixels up per frame
            )
            track.add_vote(vote)

        # Should detect upward velocity
        assert track.velocity_y < 0
        assert abs(track.velocity_y) > 5  # Approximately -10

    def test_predicted_position(self):
        """Given track with velocity, expect position prediction."""
        track = TrackedDamage(track_id=1)

        for i in range(3):
            vote = OcrVote(
                frame_index=i,
                parsed_value=1234,
                confidence=0.85,
                center_x=500.0,
                center_y=300.0 - i * 5,
            )
            track.add_vote(vote)

        # Predict position 2 frames ahead
        pred_x, pred_y = track.get_predicted_position(5)

        assert pred_x == 500.0  # No horizontal movement
        assert pred_y < 300.0  # Should be higher (lower y)

    def test_to_dict(self):
        """Given track, expect dict conversion."""
        track = TrackedDamage(track_id=1)
        track.add_vote(OcrVote(
            frame_index=10,
            parsed_value=1234,
            confidence=0.85,
            center_x=500.0,
            center_y=300.0,
        ))

        data = track.to_dict()
        assert data["track_id"] == 1
        assert data["vote_count"] == 1


class TestOcrVoteAggregator:
    """Tests for OcrVoteAggregator."""

    def test_aggregator_creation(self):
        """Given aggregator created, expect initialized."""
        aggregator = OcrVoteAggregator()
        assert aggregator.spatial_threshold == 70.0
        assert aggregator.frame_window == 5
        assert aggregator.min_votes == 2

    def test_add_vote(self):
        """Given vote added, expect stored."""
        aggregator = OcrVoteAggregator()

        aggregator.add_vote(
            value=1234,
            confidence=0.85,
            center_x=500.0,
            center_y=300.0,
            frame=10,
        )

        assert len(aggregator.votes) == 1
        assert len(aggregator.tracks) == 1

    def test_add_votes_same_track(self):
        """Given spatially close votes, expect same track."""
        aggregator = OcrVoteAggregator(spatial_threshold=70.0)

        aggregator.add_vote(value=1234, confidence=0.85, center_x=500.0, center_y=300.0, frame=10)
        aggregator.add_vote(value=1234, confidence=0.90, center_x=502.0, center_y=298.0, frame=11)
        aggregator.add_vote(value=1234, confidence=0.80, center_x=504.0, center_y=296.0, frame=12)

        assert len(aggregator.tracks) == 1
        track = list(aggregator.tracks.values())[0]
        assert len(track.votes) == 3

    def test_add_votes_different_tracks(self):
        """Given spatially distant votes, expect different tracks."""
        aggregator = OcrVoteAggregator(spatial_threshold=70.0)

        # First damage number
        aggregator.add_vote(value=1234, confidence=0.85, center_x=100.0, center_y=100.0, frame=10)

        # Second damage number (far away)
        aggregator.add_vote(value=5678, confidence=0.90, center_x=500.0, center_y=500.0, frame=10)

        assert len(aggregator.tracks) == 2

    def test_aggregate_simple(self):
        """Given simple votes, expect aggregation."""
        aggregator = OcrVoteAggregator(min_votes=2)

        aggregator.add_vote(value=1234, confidence=0.85, center_x=500.0, center_y=300.0, frame=10)
        aggregator.add_vote(value=1234, confidence=0.90, center_x=502.0, center_y=298.0, frame=11)
        aggregator.add_vote(value=1234, confidence=0.80, center_x=504.0, center_y=296.0, frame=12)

        results = aggregator.aggregate()

        assert len(results) == 1
        assert results[0].final_value == 1234
        assert results[0].vote_count == 3

    def test_aggregate_weighted_voting(self):
        """Given conflicting votes, expect weighted voting."""
        aggregator = OcrVoteAggregator(min_votes=2, use_weighted_voting=True)

        # Two votes for 1234 with high confidence
        aggregator.add_vote(value=1234, confidence=0.95, center_x=500.0, center_y=300.0, frame=10)
        aggregator.add_vote(value=1234, confidence=0.90, center_x=502.0, center_y=298.0, frame=11)

        # One vote for 1235 with low confidence
        aggregator.add_vote(value=1235, confidence=0.50, center_x=504.0, center_y=296.0, frame=12)

        results = aggregator.aggregate()

        assert len(results) == 1
        assert results[0].final_value == 1234
        assert results[0].vote_count == 2

    def test_aggregate_majority_voting(self):
        """Given conflicting votes, expect majority voting."""
        aggregator = OcrVoteAggregator(min_votes=2, use_weighted_voting=False)

        # Three votes for 1234
        for i in range(3):
            aggregator.add_vote(
                value=1234,
                confidence=0.70,
                center_x=500.0 + i * 2,
                center_y=300.0 - i * 2,
                frame=10 + i,
            )

        # Two votes for 1235
        for i in range(2):
            aggregator.add_vote(
                value=1235,
                confidence=0.90,
                center_x=500.0 + i * 2,
                center_y=300.0 - i * 2,
                frame=13 + i,
            )

        results = aggregator.aggregate()

        assert len(results) == 1
        assert results[0].final_value == 1234  # Majority wins

    def test_min_votes_filter(self):
        """Given track with insufficient votes, expect filtered."""
        aggregator = OcrVoteAggregator(min_votes=3)

        # Only 2 votes - should be filtered
        aggregator.add_vote(value=1234, confidence=0.85, center_x=500.0, center_y=300.0, frame=10)
        aggregator.add_vote(value=1234, confidence=0.90, center_x=502.0, center_y=298.0, frame=11)

        results = aggregator.aggregate()

        assert len(results) == 0

    def test_spatial_threshold(self):
        """Given votes outside threshold, expect separate tracks."""
        aggregator = OcrVoteAggregator(spatial_threshold=50.0)

        aggregator.add_vote(value=1234, confidence=0.85, center_x=0.0, center_y=0.0, frame=10)
        aggregator.add_vote(value=1234, confidence=0.90, center_x=100.0, center_y=100.0, frame=11)

        assert len(aggregator.tracks) == 2

    def test_frame_window(self):
        """Given votes outside frame window, expect separate handling."""
        aggregator = OcrVoteAggregator(frame_window=3)

        aggregator.add_vote(value=1234, confidence=0.85, center_x=500.0, center_y=300.0, frame=10)
        aggregator.add_vote(value=1234, confidence=0.90, center_x=502.0, center_y=298.0, frame=11)
        aggregator.add_vote(value=1234, confidence=0.80, center_x=504.0, center_y=296.0, frame=20)  # Too far

        # Third vote should create new track
        assert len(aggregator.tracks) == 2

    def test_prune_old_tracks(self):
        """Given old tracks, expect pruning."""
        aggregator = OcrVoteAggregator()

        aggregator.add_vote(value=1234, confidence=0.85, center_x=500.0, center_y=300.0, frame=10)
        aggregator.add_vote(value=5678, confidence=0.90, center_x=600.0, center_y=400.0, frame=50)

        pruned = aggregator.prune_old_tracks(current_frame=60, max_age=30)

        # First track (last seen at frame 10) should be pruned
        assert pruned == 1
        assert len(aggregator.tracks) == 1

    def test_get_statistics(self):
        """Given votes, expect statistics."""
        aggregator = OcrVoteAggregator()

        for i in range(5):
            aggregator.add_vote(
                value=1234,
                confidence=0.85,
                center_x=500.0 + i,
                center_y=300.0 - i,
                frame=10 + i,
            )

        stats = aggregator.get_statistics()

        assert stats["total_votes"] == 5
        assert stats["total_tracks"] == 1
        assert stats["avg_votes_per_track"] == 5.0

    def test_clear(self):
        """Given clear called, expect reset."""
        aggregator = OcrVoteAggregator()

        aggregator.add_vote(value=1234, confidence=0.85, center_x=500.0, center_y=300.0, frame=10)
        aggregator.add_vote(value=1234, confidence=0.90, center_x=502.0, center_y=298.0, frame=11)

        aggregator.clear()

        assert len(aggregator.votes) == 0
        assert len(aggregator.tracks) == 0

    def test_get_track_by_id(self):
        """Given track ID, expect track retrieval."""
        aggregator = OcrVoteAggregator()

        aggregator.add_vote(value=1234, confidence=0.85, center_x=500.0, center_y=300.0, frame=10)

        track = aggregator.get_track_by_id(1)

        assert track is not None
        assert track.track_id == 1


class TestAggregateOcrResults:
    """Tests for aggregate_ocr_results convenience function."""

    def test_aggregate_detections(self):
        """Given detections, expect aggregation."""
        detections = [
            {"frame": 10, "value": 1234, "confidence": 0.85, "center_x": 500.0, "center_y": 300.0},
            {"frame": 11, "value": 1234, "confidence": 0.90, "center_x": 502.0, "center_y": 298.0},
            {"frame": 12, "value": 1234, "confidence": 0.80, "center_x": 504.0, "center_y": 296.0},
        ]

        results = aggregate_ocr_results(detections, min_votes=2)

        assert len(results) == 1
        assert results[0].final_value == 1234

    def test_aggregate_empty(self):
        """Given empty detections, expect empty results."""
        results = aggregate_ocr_results([])
        assert len(results) == 0

    def test_aggregate_custom_parameters(self):
        """Given custom parameters, expect used."""
        detections = [
            {"frame": 10, "value": 1234, "confidence": 0.85, "center_x": 500.0, "center_y": 300.0},
            {"frame": 11, "value": 1234, "confidence": 0.90, "center_x": 502.0, "center_y": 298.0},
        ]

        results = aggregate_ocr_results(
            detections,
            spatial_threshold=100.0,
            frame_window=10,
            min_votes=2,
        )

        assert len(results) == 1
