"""Multi-frame OCR voting for consistent damage value detection.

Aggregates OCR results across multiple frames to improve accuracy
and reduce single-frame OCR errors.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class OcrVote:
    """Single OCR vote from one frame.

    Attributes:
        frame_index: Frame number where OCR was performed.
        parsed_value: Parsed damage value.
        confidence: Confidence score for this vote.
        center_x: X coordinate of detection center.
        center_y: Y coordinate of detection center.
        raw_text: Raw OCR text.
        width: Bounding box width.
        height: Bounding box height.
    """

    frame_index: int
    parsed_value: int
    confidence: float
    center_x: float
    center_y: float
    raw_text: str = ""
    width: int = 0
    height: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "frame_index": self.frame_index,
            "parsed_value": self.parsed_value,
            "confidence": round(self.confidence, 4),
            "center_x": round(self.center_x, 2),
            "center_y": round(self.center_y, 2),
            "raw_text": self.raw_text,
            "width": self.width,
            "height": self.height,
        }


@dataclass(frozen=True)
class OcrVoteResult:
    """Result of aggregating OCR votes.

    Attributes:
        final_value: Final agreed-upon damage value.
        confidence: Aggregated confidence score.
        vote_count: Number of votes that agreed.
        total_votes: Total number of votes considered.
        agreement_ratio: Ratio of agreeing votes to total.
        values_seen: All unique values that were voted.
        frames: Frame indices where votes occurred.
        method: Aggregation method used.
    """

    final_value: int
    confidence: float
    vote_count: int
    total_votes: int
    agreement_ratio: float
    values_seen: list[int]
    frames: list[int]
    method: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "final_value": self.final_value,
            "confidence": round(self.confidence, 4),
            "vote_count": self.vote_count,
            "total_votes": self.total_votes,
            "agreement_ratio": round(self.agreement_ratio, 4),
            "values_seen": self.values_seen,
            "frames": self.frames,
            "method": self.method,
        }


@dataclass
class TrackedDamage:
    """Tracks a damage number across multiple frames.

    Attributes:
        track_id: Unique identifier for this track.
        votes: All OCR votes for this track.
        first_frame: First frame where damage was seen.
        last_frame: Last frame where damage was seen.
        position_history: History of positions.
        velocity_y: Vertical velocity (pixels per frame).
        velocity_x: Horizontal velocity (pixels per frame).
    """

    track_id: int
    votes: list[OcrVote] = field(default_factory=list)
    first_frame: int = 0
    last_frame: int = 0
    position_history: list[tuple[float, float]] = field(default_factory=list)
    velocity_y: float = 0.0
    velocity_x: float = 0.0

    def add_vote(self, vote: OcrVote) -> None:
        """Add a vote to this track.

        Args:
            vote: OCR vote to add.
        """
        self.votes.append(vote)
        self.position_history.append((vote.center_x, vote.center_y))

        if not self.first_frame or vote.frame_index < self.first_frame:
            self.first_frame = vote.frame_index
        if not self.last_frame or vote.frame_index > self.last_frame:
            self.last_frame = vote.frame_index

        self._update_velocity()

    def _update_velocity(self) -> None:
        """Update velocity estimates based on position history."""
        if len(self.position_history) < 2:
            return

        # Calculate average velocity
        total_dx = 0.0
        total_dy = 0.0
        count = 0

        for i in range(1, len(self.position_history)):
            prev_x, prev_y = self.position_history[i - 1]
            curr_x, curr_y = self.position_history[i]

            # Frame difference
            prev_frame = self.votes[i - 1].frame_index
            curr_frame = self.votes[i].frame_index
            frame_diff = max(curr_frame - prev_frame, 1)

            total_dx += (curr_x - prev_x) / frame_diff
            total_dy += (curr_y - prev_y) / frame_diff
            count += 1

        if count > 0:
            self.velocity_x = total_dx / count
            self.velocity_y = total_dy / count

    def get_predicted_position(self, frame: int) -> tuple[float, float]:
        """Predict position at given frame.

        Args:
            frame: Target frame index.

        Returns:
            Predicted (x, y) position.
        """
        if not self.votes:
            return (0.0, 0.0)

        # Use last known position and velocity
        last_vote = self.votes[-1]
        frames_ahead = frame - last_vote.frame_index

        pred_x = last_vote.center_x + self.velocity_x * frames_ahead
        pred_y = last_vote.center_y + self.velocity_y * frames_ahead

        return (pred_x, pred_y)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "track_id": self.track_id,
            "vote_count": len(self.votes),
            "first_frame": self.first_frame,
            "last_frame": self.last_frame,
            "velocity_x": round(self.velocity_x, 2),
            "velocity_y": round(self.velocity_y, 2),
            "votes": [v.to_dict() for v in self.votes],
        }


class OcrVoteAggregator:
    """Aggregates OCR votes across multiple frames.

    Uses spatial proximity and temporal continuity to group
    votes from the same damage number, then applies voting
    to determine the most likely value.

    Example:
        aggregator = OcrVoteAggregator(
            spatial_threshold=70.0,
            frame_window=5,
            min_votes=2,
        )

        # Add votes from multiple frames
        aggregator.add_vote(1, 1234, 0.85, 500.0, 300.0, frame=10)
        aggregator.add_vote(1, 1234, 0.90, 502.0, 298.0, frame=11)
        aggregator.add_vote(1, 1235, 0.75, 504.0, 296.0, frame=12)

        # Get aggregated results
        results = aggregator.aggregate()
        for result in results:
            print(f"Value: {result.final_value}, Confidence: {result.confidence}")
    """

    def __init__(
        self,
        spatial_threshold: float = 70.0,
        frame_window: int = 5,
        min_votes: int = 2,
        value_tolerance: float = 0.05,
        use_weighted_voting: bool = True,
    ) -> None:
        """Initialize OCR vote aggregator.

        Args:
            spatial_threshold: Maximum pixel distance for vote grouping.
            frame_window: Maximum frame span for vote grouping.
            min_votes: Minimum votes required for aggregation.
            value_tolerance: Tolerance for value matching (as fraction).
            use_weighted_voting: Use confidence-weighted voting.
        """
        self.spatial_threshold = spatial_threshold
        self.frame_window = frame_window
        self.min_votes = min_votes
        self.value_tolerance = value_tolerance
        self.use_weighted_voting = use_weighted_voting

        # Vote storage
        self.votes: list[OcrVote] = []
        self.tracks: dict[int, TrackedDamage] = {}
        self.next_track_id = 1

    def add_vote(
        self,
        value: int,
        confidence: float,
        center_x: float,
        center_y: float,
        frame: int,
        raw_text: str = "",
        width: int = 0,
        height: int = 0,
    ) -> None:
        """Add a vote from a frame.

        Args:
            value: Parsed damage value.
            confidence: Confidence score.
            center_x: X coordinate of center.
            center_y: Y coordinate of center.
            frame: Frame index.
            raw_text: Raw OCR text.
            width: Bounding box width.
            height: Bounding box height.
        """
        vote = OcrVote(
            frame_index=frame,
            parsed_value=value,
            confidence=confidence,
            center_x=center_x,
            center_y=center_y,
            raw_text=raw_text,
            width=width,
            height=height,
        )
        self.votes.append(vote)

        # Try to assign to existing track
        track = self._find_matching_track(vote)
        if track is None:
            # Create new track
            track = TrackedDamage(track_id=self.next_track_id)
            self.next_track_id += 1
            self.tracks[track.track_id] = track

        track.add_vote(vote)

    def _find_matching_track(self, vote: OcrVote) -> TrackedDamage | None:
        """Find existing track that matches this vote.

        Args:
            vote: Vote to match.

        Returns:
            Matching track or None.
        """
        for track in self.tracks.values():
            # Check frame window
            if vote.frame_index - track.last_frame > self.frame_window:
                continue

            # Check spatial proximity
            if track.votes:
                last_vote = track.votes[-1]
                distance = (
                    (vote.center_x - last_vote.center_x) ** 2 +
                    (vote.center_y - last_vote.center_y) ** 2
                ) ** 0.5

                if distance > self.spatial_threshold:
                    continue

                # Check value similarity
                if last_vote.parsed_value > 0:
                    value_diff = abs(vote.parsed_value - last_vote.parsed_value) / last_vote.parsed_value
                    if value_diff > self.value_tolerance:
                        continue

            return track

        return None

    def aggregate(self) -> list[OcrVoteResult]:
        """Aggregate votes into final results.

        Returns:
            List of OcrVoteResult objects.
        """
        results: list[OcrVoteResult] = []

        for track in self.tracks.values():
            if len(track.votes) < self.min_votes:
                continue

            result = self._aggregate_track(track)
            results.append(result)

        return results

    def _aggregate_track(self, track: TrackedDamage) -> OcrVoteResult:
        """Aggregate votes within a single track.

        Args:
            track: Track to aggregate.

        Returns:
            OcrVoteResult for the track.
        """
        votes = track.votes

        # Group votes by value
        value_groups: dict[int, list[OcrVote]] = defaultdict(list)
        for vote in votes:
            value_groups[vote.parsed_value].append(vote)

        # Find winning value
        if self.use_weighted_voting:
            # Weighted by confidence
            value_weights: dict[int, float] = {}
            for value, group_votes in value_groups.items():
                weight = sum(v.confidence for v in group_votes)
                value_weights[value] = weight

            winning_value = max(value_weights.keys(), key=lambda v: value_weights[v])
            total_weight = sum(value_weights.values())
            winning_weight = value_weights[winning_value]
        else:
            # Simple majority
            winning_value = max(value_groups.keys(), key=lambda v: len(value_groups[v]))
            total_weight = len(votes)
            winning_weight = len(value_groups[winning_value])

        # Calculate statistics
        values_seen = list(value_groups.keys())
        frames = sorted(set(v.frame_index for v in votes))

        agreement_ratio = winning_weight / total_weight if total_weight > 0 else 0.0

        # Calculate final confidence
        winning_votes = value_groups[winning_value]
        avg_confidence = sum(v.confidence for v in winning_votes) / len(winning_votes)
        final_confidence = avg_confidence * agreement_ratio

        return OcrVoteResult(
            final_value=winning_value,
            confidence=final_confidence,
            vote_count=len(winning_votes),
            total_votes=len(votes),
            agreement_ratio=agreement_ratio,
            values_seen=values_seen,
            frames=frames,
            method="weighted_voting" if self.use_weighted_voting else "majority_voting",
        )

    def get_tracks(self) -> list[TrackedDamage]:
        """Get all damage tracks.

        Returns:
            List of TrackedDamage objects.
        """
        return list(self.tracks.values())

    def get_track_by_id(self, track_id: int) -> TrackedDamage | None:
        """Get track by ID.

        Args:
            track_id: Track identifier.

        Returns:
            TrackedDamage or None.
        """
        return self.tracks.get(track_id)

    def clear(self) -> None:
        """Clear all votes and tracks."""
        self.votes.clear()
        self.tracks.clear()
        self.next_track_id = 1

    def prune_old_tracks(self, current_frame: int, max_age: int = 30) -> int:
        """Remove tracks that haven't been updated recently.

        Args:
            current_frame: Current frame index.
            max_age: Maximum frames since last update.

        Returns:
            Number of tracks pruned.
        """
        pruned = 0
        to_remove = []

        for track_id, track in self.tracks.items():
            if current_frame - track.last_frame > max_age:
                to_remove.append(track_id)
                pruned += 1

        for track_id in to_remove:
            del self.tracks[track_id]

        return pruned

    def get_statistics(self) -> dict[str, Any]:
        """Get aggregator statistics.

        Returns:
            Dictionary of statistics.
        """
        vote_counts = [len(t.votes) for t in self.tracks.values()]

        return {
            "total_votes": len(self.votes),
            "total_tracks": len(self.tracks),
            "avg_votes_per_track": sum(vote_counts) / len(vote_counts) if vote_counts else 0,
            "max_votes_per_track": max(vote_counts) if vote_counts else 0,
            "min_votes_per_track": min(vote_counts) if vote_counts else 0,
        }


def aggregate_ocr_results(
    detections: list[dict[str, Any]],
    spatial_threshold: float = 70.0,
    frame_window: int = 5,
    min_votes: int = 2,
) -> list[OcrVoteResult]:
    """Convenience function to aggregate OCR results.

    Args:
        detections: List of detection dictionaries with keys:
            - frame: Frame index
            - value: Parsed damage value
            - confidence: Confidence score
            - center_x: X coordinate
            - center_y: Y coordinate
            - raw_text: Raw OCR text (optional)
        spatial_threshold: Maximum pixel distance for grouping.
        frame_window: Maximum frame span for grouping.
        min_votes: Minimum votes for aggregation.

    Returns:
        List of OcrVoteResult objects.
    """
    aggregator = OcrVoteAggregator(
        spatial_threshold=spatial_threshold,
        frame_window=frame_window,
        min_votes=min_votes,
    )

    for det in detections:
        aggregator.add_vote(
            value=det.get("value", 0),
            confidence=det.get("confidence", 0.5),
            center_x=det.get("center_x", 0),
            center_y=det.get("center_y", 0),
            frame=det.get("frame", 0),
            raw_text=det.get("raw_text", ""),
        )

    return aggregator.aggregate()
