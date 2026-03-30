"""Frame snapshot capture for detection troubleshooting.

Captures and saves frame images when detections succeed or fail.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image


@dataclass
class SnapshotMetadata:
    """Metadata for a captured snapshot.

    Attributes:
        snapshot_path: Path to the snapshot file.
        frame_index: Frame number.
        timestamp: ISO 8601 timestamp.
        session_id: Session identifier.
        reason: Reason for capturing (e.g., "rejection", "acceptance").
        candidate_count: Number of candidates in frame.
        accepted_count: Number of accepted candidates.
        rejected_count: Number of rejected candidates.
        processing_time_ms: Processing time for the frame.
        additional_info: Additional metadata.
    """

    snapshot_path: str
    frame_index: int
    timestamp: str
    session_id: str
    reason: str
    candidate_count: int
    accepted_count: int
    rejected_count: int
    processing_time_ms: float
    additional_info: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "snapshot_path": self.snapshot_path,
            "frame_index": self.frame_index,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "reason": self.reason,
            "candidate_count": self.candidate_count,
            "accepted_count": self.accepted_count,
            "rejected_count": self.rejected_count,
            "processing_time_ms": round(self.processing_time_ms, 3),
        }
        if self.additional_info:
            result["additional_info"] = self.additional_info
        return result

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


class SnapshotCapture:
    """Captures and saves frame snapshots for troubleshooting.

    Example:
        capture = SnapshotCapture(
            session_id="session_001",
            snapshot_dir=Path("snapshots"),
            max_snapshots=100,
            compress=True,
        )

        # Capture on rejection
        capture.capture(
            image=frame_image,
            frame_index=100,
            reason="rejection",
            candidates=[...],
            accepted=[],
            rejected=[...],
            processing_time_ms=45.2,
        )
    """

    def __init__(
        self,
        session_id: str,
        snapshot_dir: Path | str | None = None,
        max_snapshots: int = 100,
        compress: bool = True,
        quality: int = 85,
        include_metadata: bool = True,
    ) -> None:
        """Initialize snapshot capture.

        Args:
            session_id: Session identifier.
            snapshot_dir: Directory for snapshots. Defaults to snapshots/<session_id>/.
            max_snapshots: Maximum snapshots to keep (oldest removed).
            compress: Whether to compress snapshots (JPEG vs PNG).
            quality: JPEG quality (1-100) if compress=True.
            include_metadata: Whether to save metadata JSON alongside images.
        """
        self.session_id = session_id
        self.snapshot_dir = (
            Path(snapshot_dir) / session_id
            if snapshot_dir
            else Path("snapshots") / session_id
        )
        self.max_snapshots = max_snapshots
        self.compress = compress
        self.quality = quality
        self.include_metadata = include_metadata

        # Create directory
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

        # Track captured snapshots
        self.captured_snapshots: list[SnapshotMetadata] = []
        self.snapshot_count = 0

    def capture(
        self,
        image: Image.Image,
        frame_index: int,
        reason: str,
        candidate_count: int,
        accepted_count: int,
        rejected_count: int,
        processing_time_ms: float,
        additional_info: dict[str, Any] | None = None,
    ) -> SnapshotMetadata | None:
        """Capture and save a frame snapshot.

        Args:
            image: Frame image to save.
            frame_index: Frame number.
            reason: Reason for capturing (e.g., "rejection", "acceptance", "debug").
            candidate_count: Number of candidates in frame.
            accepted_count: Number of accepted candidates.
            rejected_count: Number of rejected candidates.
            processing_time_ms: Processing time for the frame.
            additional_info: Additional metadata to save.

        Returns:
            SnapshotMetadata if captured, None if skipped (max reached).
        """
        # Check max snapshots
        if self.snapshot_count >= self.max_snapshots:
            return None

        # Generate filename
        timestamp = datetime.now()
        filename = f"{self.session_id}_frame{frame_index:06d}_{reason}_{timestamp.strftime('%H%M%S')}"
        extension = "jpg" if self.compress else "png"
        snapshot_path = self.snapshot_dir / f"{filename}.{extension}"

        # Save image
        save_kwargs = {"quality": self.quality} if self.compress else {}
        image.save(snapshot_path, **save_kwargs)

        # Create metadata
        metadata = SnapshotMetadata(
            snapshot_path=str(snapshot_path),
            frame_index=frame_index,
            timestamp=timestamp.isoformat(),
            session_id=self.session_id,
            reason=reason,
            candidate_count=candidate_count,
            accepted_count=accepted_count,
            rejected_count=rejected_count,
            processing_time_ms=processing_time_ms,
            additional_info=additional_info,
        )

        # Save metadata JSON
        if self.include_metadata:
            metadata_path = self.snapshot_dir / f"{filename}.json"
            with open(metadata_path, "w", encoding="utf-8") as f:
                f.write(metadata.to_json())

        # Track snapshot
        self.captured_snapshots.append(metadata)
        self.snapshot_count += 1

        return metadata

    def capture_rejection(
        self,
        image: Image.Image,
        frame_index: int,
        rejected_candidates: list[dict[str, Any]],
        processing_time_ms: float,
    ) -> SnapshotMetadata | None:
        """Capture snapshot for rejected candidates.

        Args:
            image: Frame image.
            frame_index: Frame number.
            rejected_candidates: List of rejected candidate dictionaries.
            processing_time_ms: Processing time.

        Returns:
            SnapshotMetadata if captured.
        """
        return self.capture(
            image=image,
            frame_index=frame_index,
            reason="rejection",
            candidate_count=len(rejected_candidates),
            accepted_count=0,
            rejected_count=len(rejected_candidates),
            processing_time_ms=processing_time_ms,
            additional_info={
                "rejected_candidates": rejected_candidates,
                "capture_trigger": "rejection",
            },
        )

    def capture_acceptance(
        self,
        image: Image.Image,
        frame_index: int,
        accepted_candidates: list[dict[str, Any]],
        processing_time_ms: float,
    ) -> SnapshotMetadata | None:
        """Capture snapshot for accepted candidates.

        Args:
            image: Frame image.
            frame_index: Frame number.
            accepted_candidates: List of accepted candidate dictionaries.
            processing_time_ms: Processing time.

        Returns:
            SnapshotMetadata if captured.
        """
        return self.capture(
            image=image,
            frame_index=frame_index,
            reason="acceptance",
            candidate_count=len(accepted_candidates),
            accepted_count=len(accepted_candidates),
            rejected_count=0,
            processing_time_ms=processing_time_ms,
            additional_info={
                "accepted_candidates": accepted_candidates,
                "capture_trigger": "acceptance",
            },
        )

    def capture_debug(
        self,
        image: Image.Image,
        frame_index: int,
        debug_info: dict[str, Any],
    ) -> SnapshotMetadata | None:
        """Capture debug snapshot with custom information.

        Args:
            image: Frame image.
            frame_index: Frame number.
            debug_info: Custom debug information.

        Returns:
            SnapshotMetadata if captured.
        """
        return self.capture(
            image=image,
            frame_index=frame_index,
            reason="debug",
            candidate_count=debug_info.get("candidate_count", 0),
            accepted_count=debug_info.get("accepted_count", 0),
            rejected_count=debug_info.get("rejected_count", 0),
            processing_time_ms=debug_info.get("processing_time_ms", 0.0),
            additional_info={
                **debug_info,
                "capture_trigger": "debug",
            },
        )

    def get_snapshot_index(self) -> list[dict[str, Any]]:
        """Get index of all captured snapshots.

        Returns:
            List of snapshot metadata dictionaries.
        """
        return [s.to_dict() for s in self.captured_snapshots]

    def save_snapshot_index(self, output_path: Path | str) -> None:
        """Save snapshot index to JSON file.

        Args:
            output_path: Path to output file.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        index = self.get_snapshot_index()
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2)

    def cleanup_old_snapshots(self) -> int:
        """Remove oldest snapshots if over max_snapshots.

        Returns:
            Number of snapshots removed.
        """
        removed = 0
        while len(self.captured_snapshots) > self.max_snapshots:
            oldest = self.captured_snapshots.pop(0)
            snapshot_path = Path(oldest.snapshot_path)
            metadata_path = snapshot_path.with_suffix(".json")

            if snapshot_path.exists():
                snapshot_path.unlink()
                removed += 1

            if metadata_path.exists():
                metadata_path.unlink()

        return removed

    def get_statistics(self) -> dict[str, Any]:
        """Get snapshot statistics.

        Returns:
            Dictionary with statistics.
        """
        by_reason: dict[str, int] = {}
        for snapshot in self.captured_snapshots:
            by_reason[snapshot.reason] = by_reason.get(snapshot.reason, 0) + 1

        return {
            "total_snapshots": self.snapshot_count,
            "max_snapshots": self.max_snapshots,
            "snapshot_directory": str(self.snapshot_dir),
            "by_reason": by_reason,
            "disk_usage_estimate_mb": self._estimate_disk_usage(),
        }

    def _estimate_disk_usage(self) -> float:
        """Estimate total disk usage in MB.

        Returns:
            Estimated disk usage in megabytes.
        """
        total_bytes = 0
        for snapshot in self.captured_snapshots:
            path = Path(snapshot.snapshot_path)
            if path.exists():
                total_bytes += path.stat().st_size

            # Add metadata file size
            metadata_path = path.with_suffix(".json")
            if metadata_path.exists():
                total_bytes += metadata_path.stat().st_size

        return total_bytes / (1024 * 1024)


class SnapshotStrategy:
    """Configurable snapshot capture strategy.

    Defines when to capture snapshots based on detection results.
    """

    def __init__(
        self,
        capture_on_rejection: bool = True,
        capture_on_acceptance: bool = False,
        capture_on_low_confidence: bool = True,
        low_confidence_threshold: float = 0.65,
        capture_on_high_confidence: bool = False,
        high_confidence_threshold: float = 0.95,
        capture_every_n_frames: int = 0,  # 0 = disabled
        max_snapshots_per_session: int = 100,
    ) -> None:
        """Initialize snapshot strategy.

        Args:
            capture_on_rejection: Capture when candidates are rejected.
            capture_on_acceptance: Capture when candidates are accepted.
            capture_on_low_confidence: Capture on low confidence detections.
            low_confidence_threshold: Threshold for low confidence.
            capture_on_high_confidence: Capture on very high confidence.
            high_confidence_threshold: Threshold for high confidence.
            capture_every_n_frames: Capture every N frames (0 = disabled).
            max_snapshots_per_session: Maximum snapshots per session.
        """
        self.capture_on_rejection = capture_on_rejection
        self.capture_on_acceptance = capture_on_acceptance
        self.capture_on_low_confidence = capture_on_low_confidence
        self.low_confidence_threshold = low_confidence_threshold
        self.capture_on_high_confidence = capture_on_high_confidence
        self.high_confidence_threshold = high_confidence_threshold
        self.capture_every_n_frames = capture_every_n_frames
        self.max_snapshots_per_session = max_snapshots_per_session

    def should_capture(
        self,
        frame_index: int,
        accepted_count: int,
        rejected_count: int,
        max_confidence: float,
    ) -> tuple[bool, str]:
        """Determine if snapshot should be captured.

        Args:
            frame_index: Frame number.
            accepted_count: Number of accepted candidates.
            rejected_count: Number of rejected candidates.
            max_confidence: Maximum confidence in frame.

        Returns:
            Tuple of (should_capture, reason).
        """
        # Check periodic capture
        if (
            self.capture_every_n_frames > 0
            and frame_index % self.capture_every_n_frames == 0
        ):
            return True, "periodic"

        # Check rejection capture
        if self.capture_on_rejection and rejected_count > 0:
            return True, "rejection"

        # Check acceptance capture
        if self.capture_on_acceptance and accepted_count > 0:
            return True, "acceptance"

        # Check low confidence capture
        if (
            self.capture_on_low_confidence
            and max_confidence < self.low_confidence_threshold
            and max_confidence > 0.0
        ):
            return True, "low_confidence"

        # Check high confidence capture
        if (
            self.capture_on_high_confidence
            and max_confidence >= self.high_confidence_threshold
        ):
            return True, "high_confidence"

        return False, ""
