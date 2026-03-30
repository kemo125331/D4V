"""Logging infrastructure for D4V detection.

This package provides:
- Structured logging of detection decisions
- Frame snapshot capture on events
- Session-level metrics aggregation

Example:
    from d4v.logging import (
        DetectionLogger,
        SnapshotCapture,
        MetricsLogger,
        RejectionReason,
    )

    # Create detection logger
    logger = DetectionLogger(
        session_id="session_001",
        snapshot_on_rejection=True,
    )

    # Log frame results
    logger.log_frame(
        frame_index=100,
        timestamp_ms=3333,
        candidates=[...],
        accepted=[...],
        rejected=[...],
        processing_time_ms=45.2,
    )

    # Print summary
    logger.print_summary()
"""

from d4v.logging.detection_logger import (
    AcceptanceEntry,
    AcceptanceReason,
    CandidateInfo,
    DetectionLogEntry,
    DetectionLogger,
    DetectionLoggerFactory,
    RejectionEntry,
    RejectionReason,
)
from d4v.logging.metrics_logger import (
    MetricsLogger,
    MetricsLoggerFactory,
    SessionMetrics,
)
from d4v.logging.snapshot_capture import (
    SnapshotCapture,
    SnapshotMetadata,
    SnapshotStrategy,
)

__all__ = [
    # Detection Logger
    "DetectionLogger",
    "DetectionLoggerFactory",
    "DetectionLogEntry",
    "RejectionReason",
    "AcceptanceReason",
    "RejectionEntry",
    "AcceptanceEntry",
    "CandidateInfo",
    # Snapshot Capture
    "SnapshotCapture",
    "SnapshotMetadata",
    "SnapshotStrategy",
    # Metrics Logger
    "MetricsLogger",
    "MetricsLoggerFactory",
    "SessionMetrics",
]
