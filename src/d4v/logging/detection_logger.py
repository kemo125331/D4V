"""Structured logging for detection decisions and troubleshooting.

Provides comprehensive logging of all detection decisions with rejection reasons.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any


class RejectionReason(StrEnum):
    """Reasons for rejecting a detection candidate."""

    LOW_CONFIDENCE = "low_confidence"
    IMPLAUSIBLE_TEXT = "implausible_text"
    DUPLICATE = "duplicate"
    INVALID_PARSE = "invalid_parse"
    SIZE_CONSTRAINT = "size_constraint"
    COLOR_MISMATCH = "color_mismatch"
    SPATIAL_OUTLIER = "spatial_outlier"
    TEMPORAL_OUTLIER = "temporal_outlier"
    OCCLUSION = "occlusion"
    MOTION_BLUR = "motion_blur"


class AcceptanceReason(StrEnum):
    """Reasons for accepting a detection."""

    HIGH_CONFIDENCE = "high_confidence"
    CONSISTENT_TRACK = "consistent_track"
    MULTI_FRAME_CONFIRM = "multi_frame_confirm"
    USER_VERIFIED = "user_verified"


@dataclass(frozen=True)
class CandidateInfo:
    """Information about a detection candidate.

    Attributes:
        center_x: X coordinate of candidate center.
        center_y: Y coordinate of candidate center.
        width: Bounding box width.
        height: Bounding box height.
        raw_text: Raw OCR text output.
        parsed_value: Parsed damage value (if successful).
        confidence: Confidence score before thresholds.
        member_count: Number of connected components in candidate.
    """

    center_x: float
    center_y: float
    width: int
    height: int
    raw_text: str
    parsed_value: int | None
    confidence: float
    member_count: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class DetectionLogEntry:
    """Single detection decision log entry.

    Attributes:
        timestamp: ISO 8601 timestamp of the log entry.
        frame_index: Frame number in the session.
        timestamp_ms: Timestamp in milliseconds (if available).
        session_id: Unique session identifier.
        candidates_examined: Number of candidates considered.
        hits_accepted: Number of hits accepted.
        hits_rejected: List of rejection reasons for rejected candidates.
        accepted_candidates: Details of accepted candidates.
        rejected_candidates: Details of rejected candidates with reasons.
        processing_time_ms: Time spent processing this frame.
        snapshot_path: Path to frame snapshot (if captured).
        metadata: Additional metadata.
    """

    timestamp: str
    frame_index: int
    timestamp_ms: int | None
    session_id: str
    candidates_examined: int
    hits_accepted: int
    hits_rejected: int
    accepted_candidates: list[dict[str, Any]] = field(default_factory=list)
    rejected_candidates: list[dict[str, Any]] = field(default_factory=list)
    processing_time_ms: float = 0.0
    snapshot_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp,
            "frame_index": self.frame_index,
            "timestamp_ms": self.timestamp_ms,
            "session_id": self.session_id,
            "candidates_examined": self.candidates_examined,
            "hits_accepted": self.hits_accepted,
            "hits_rejected": self.hits_rejected,
            "accepted_candidates": self.accepted_candidates,
            "rejected_candidates": self.rejected_candidates,
            "processing_time_ms": round(self.processing_time_ms, 3),
            "snapshot_path": self.snapshot_path,
            "metadata": self.metadata,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


@dataclass
class RejectionEntry:
    """A rejected candidate with reasons.

    Attributes:
        candidate: Candidate information.
        reasons: List of rejection reasons.
        confidence: Confidence score.
        snapshot_available: Whether a snapshot was captured.
    """

    candidate: CandidateInfo
    reasons: list[RejectionReason]
    confidence: float
    snapshot_available: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "candidate": self.candidate.to_dict(),
            "reasons": [str(r) for r in self.reasons],
            "confidence": round(self.confidence, 4),
            "snapshot_available": self.snapshot_available,
        }


@dataclass
class AcceptanceEntry:
    """An accepted candidate with reasons.

    Attributes:
        candidate: Candidate information.
        reasons: List of acceptance reasons.
        final_confidence: Final confidence after all scoring.
        parsed_value: Parsed damage value.
    """

    candidate: CandidateInfo
    reasons: list[AcceptanceReason]
    final_confidence: float
    parsed_value: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "candidate": self.candidate.to_dict(),
            "reasons": [str(r) for r in self.reasons],
            "final_confidence": round(self.final_confidence, 4),
            "parsed_value": self.parsed_value,
        }


class DetectionLogger:
    """Logger for detection decisions.

    Logs all detection candidates with acceptance/rejection decisions
    for troubleshooting and analysis.

    Example:
        logger = DetectionLogger(
            session_id="session_001",
            log_dir=Path("logs/detections"),
            snapshot_on_rejection=True,
            min_confidence_to_log=0.3,
        )

        # Log a frame's detection results
        logger.log_frame(
            frame_index=100,
            timestamp_ms=3333,
            candidates=[...],
            accepted_hits=[...],
            rejected_hits=[...],
            processing_time_ms=45.2,
        )

        # Get session summary
        summary = logger.get_session_summary()
        print(f"Total candidates: {summary.total_candidates}")
        print(f"Acceptance rate: {summary.acceptance_rate:.2%}")
    """

    def __init__(
        self,
        session_id: str,
        log_dir: Path | str | None = None,
        snapshot_dir: Path | str | None = None,
        snapshot_on_rejection: bool = False,
        snapshot_on_acceptance: bool = False,
        min_confidence_to_log: float = 0.0,
        log_level: int = logging.INFO,
    ) -> None:
        """Initialize detection logger.

        Args:
            session_id: Unique session identifier.
            log_dir: Directory for log files. Defaults to logs/detections/.
            snapshot_dir: Directory for frame snapshots. Defaults to log_dir/snapshots/.
            snapshot_on_rejection: Capture snapshot when hits are rejected.
            snapshot_on_acceptance: Capture snapshot when hits are accepted.
            min_confidence_to_log: Minimum confidence to log candidate.
            log_level: Logging level for console output.
        """
        self.session_id = session_id
        self.log_dir = Path(log_dir) if log_dir else Path("logs/detections")
        self.snapshot_dir = (
            Path(snapshot_dir) if snapshot_dir else self.log_dir / "snapshots"
        )
        self.snapshot_on_rejection = snapshot_on_rejection
        self.snapshot_on_acceptance = snapshot_on_acceptance
        self.min_confidence_to_log = min_confidence_to_log

        # Create directories
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

        # Setup logging
        self.logger = logging.getLogger(f"d4v.detection.{session_id}")
        self.logger.setLevel(log_level)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_format = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S",
        )
        console_handler.setFormatter(console_format)
        self.logger.addHandler(console_handler)

        # File handler (JSON)
        self.log_file = self.log_dir / f"{session_id}.jsonl"
        self.file_handler = logging.FileHandler(self.log_file, encoding="utf-8")
        self.file_handler.setLevel(logging.DEBUG)
        self.logger.addHandler(self.file_handler)

        # Accumulated entries
        self.entries: list[DetectionLogEntry] = []
        self.total_candidates = 0
        self.total_accepted = 0
        self.total_rejected = 0
        self.rejection_reason_counts: dict[RejectionReason, int] = {}

    def log_frame(
        self,
        frame_index: int,
        timestamp_ms: int | None,
        candidates: list[CandidateInfo],
        accepted: list[AcceptanceEntry],
        rejected: list[RejectionEntry],
        processing_time_ms: float,
        snapshot_path: Path | str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DetectionLogEntry:
        """Log detection results for a frame.

        Args:
            frame_index: Frame number.
            timestamp_ms: Timestamp in milliseconds.
            candidates: All candidates examined.
            accepted: Accepted candidates with reasons.
            rejected: Rejected candidates with reasons.
            processing_time_ms: Processing time for this frame.
            snapshot_path: Optional path to frame snapshot.
            metadata: Optional additional metadata.

        Returns:
            Created DetectionLogEntry.
        """
        entry = DetectionLogEntry(
            timestamp=datetime.now().isoformat(),
            frame_index=frame_index,
            timestamp_ms=timestamp_ms,
            session_id=self.session_id,
            candidates_examined=len(candidates),
            hits_accepted=len(accepted),
            hits_rejected=len(rejected),
            accepted_candidates=[a.to_dict() for a in accepted],
            rejected_candidates=[r.to_dict() for r in rejected],
            processing_time_ms=processing_time_ms,
            snapshot_path=str(snapshot_path) if snapshot_path else None,
            metadata=metadata or {},
        )

        # Log to file
        self.file_handler.emit(
            logging.LogRecord(
                name=self.logger.name,
                level=logging.INFO,
                pathname=str(self.log_file),
                lineno=0,
                msg=entry.to_json(),
                args=(),
                exc_info=None,
            )
        )

        # Log summary to console
        self.logger.info(
            f"Frame {frame_index}: {len(accepted)}/{len(candidates)} accepted, "
            f"{len(rejected)} rejected, {processing_time_ms:.1f}ms"
        )

        # Update accumulators
        self.entries.append(entry)
        self.total_candidates += len(candidates)
        self.total_accepted += len(accepted)
        self.total_rejected += len(rejected)

        for rej in rejected:
            for reason in rej.reasons:
                self.rejection_reason_counts[reason] = (
                    self.rejection_reason_counts.get(reason, 0) + 1
                )

        return entry

    def create_rejection_entry(
        self,
        candidate: CandidateInfo,
        reasons: list[RejectionReason],
        snapshot_available: bool = False,
    ) -> RejectionEntry:
        """Create a rejection entry.

        Args:
            candidate: Candidate information.
            reasons: List of rejection reasons.
            snapshot_available: Whether snapshot was captured.

        Returns:
            RejectionEntry object.
        """
        return RejectionEntry(
            candidate=candidate,
            reasons=reasons,
            confidence=candidate.confidence,
            snapshot_available=snapshot_available,
        )

    def create_acceptance_entry(
        self,
        candidate: CandidateInfo,
        reasons: list[AcceptanceReason],
        final_confidence: float,
        parsed_value: int,
    ) -> AcceptanceEntry:
        """Create an acceptance entry.

        Args:
            candidate: Candidate information.
            reasons: List of acceptance reasons.
            final_confidence: Final confidence score.
            parsed_value: Parsed damage value.

        Returns:
            AcceptanceEntry object.
        """
        return AcceptanceEntry(
            candidate=candidate,
            reasons=reasons,
            final_confidence=final_confidence,
            parsed_value=parsed_value,
        )

    def get_session_summary(self) -> dict[str, Any]:
        """Get summary statistics for the session.

        Returns:
            Dictionary with session summary statistics.
        """
        acceptance_rate = (
            self.total_accepted / self.total_candidates
            if self.total_candidates > 0
            else 0.0
        )

        avg_processing_time = (
            sum(e.processing_time_ms for e in self.entries) / len(self.entries)
            if self.entries
            else 0.0
        )

        return {
            "session_id": self.session_id,
            "total_frames": len(self.entries),
            "total_candidates": self.total_candidates,
            "total_accepted": self.total_accepted,
            "total_rejected": self.total_rejected,
            "acceptance_rate": round(acceptance_rate, 4),
            "avg_processing_time_ms": round(avg_processing_time, 2),
            "rejection_reasons": {
                str(reason): count
                for reason, count in self.rejection_reason_counts.items()
            },
            "log_file": str(self.log_file),
            "snapshot_count": sum(
                1 for e in self.entries if e.snapshot_path is not None
            ),
        }

    def print_summary(self) -> None:
        """Print session summary to console."""
        summary = self.get_session_summary()
        print(f"\n{'='*60}")
        print(f"Detection Session Summary: {self.session_id}")
        print(f"{'='*60}")
        print(f"Total frames logged: {summary['total_frames']}")
        print(f"Total candidates: {summary['total_candidates']}")
        print(f"Accepted: {summary['total_accepted']}")
        print(f"Rejected: {summary['total_rejected']}")
        print(f"Acceptance rate: {summary['acceptance_rate']:.2%}")
        print(f"Avg processing time: {summary['avg_processing_time_ms']:.1f}ms")
        print(f"\nRejection reasons:")
        for reason, count in summary["rejection_reasons"].items():
            print(f"  {reason}: {count}")
        print(f"{'='*60}\n")

    def export_summary(self, output_path: Path | str) -> None:
        """Export session summary to JSON file.

        Args:
            output_path: Path to output file.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        summary = self.get_session_summary()
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

    def close(self) -> None:
        """Close loggers and cleanup."""
        self.file_handler.close()
        self.logger.removeHandler(self.file_handler)
        self.logger.info("Session logging complete")


class DetectionLoggerFactory:
    """Factory for creating detection loggers."""

    @staticmethod
    def create(
        session_id: str,
        config: dict[str, Any] | None = None,
    ) -> DetectionLogger:
        """Create a detection logger with configuration.

        Args:
            session_id: Session identifier.
            config: Configuration dictionary.

        Returns:
            Configured DetectionLogger instance.
        """
        config = config or {}

        return DetectionLogger(
            session_id=session_id,
            log_dir=config.get("log_dir"),
            snapshot_dir=config.get("snapshot_dir"),
            snapshot_on_rejection=config.get("snapshot_on_rejection", False),
            snapshot_on_acceptance=config.get("snapshot_on_acceptance", False),
            min_confidence_to_log=config.get("min_confidence_to_log", 0.0),
            log_level=getattr(
                logging, config.get("log_level", "INFO").upper()
            ),
        )
