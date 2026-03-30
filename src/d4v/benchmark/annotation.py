"""Annotation format and helpers for benchmark ground truth.

Defines the JSON schema for annotating replay frames with ground truth damage hits.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GroundTruthHit:
    """A single ground truth damage hit annotation.

    Attributes:
        frame: Frame index (0-based) within the replay.
        value: Damage value (integer, no suffixes).
        x: X coordinate of hit center (pixels, relative to damage ROI).
        y: Y coordinate of hit center (pixels, relative to damage ROI).
        width: Bounding box width in pixels.
        height: Bounding box height in pixels.
        damage_type: Type of damage (direct, crit, dot, etc.).
        notes: Optional annotation notes.
    """

    frame: int
    value: int
    x: float
    y: float
    width: int = 0
    height: int = 0
    damage_type: str = "direct"
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GroundTruthHit:
        """Create from dictionary (JSON deserialization)."""
        return cls(
            frame=data["frame"],
            value=data["value"],
            x=data["x"],
            y=data["y"],
            width=data.get("width", 0),
            height=data.get("height", 0),
            damage_type=data.get("damage_type", "direct"),
            notes=data.get("notes", ""),
        )


@dataclass
class BenchmarkAnnotation:
    """Complete benchmark annotation for a replay session.

    Attributes:
        session_id: Unique identifier for the replay session.
        session_name: Human-readable session name.
        description: Session description (zone, build, conditions).
        resolution: Screen resolution as "WIDTHxHEIGHT".
        ui_scale: UI scale percentage (100 = 100%).
        total_frames: Total number of frames in the replay.
        fps: Capture frame rate.
        hits: List of ground truth damage hits.
        metadata: Additional metadata (build, zone, timestamp, etc.).
    """

    session_id: str
    session_name: str
    description: str
    resolution: str
    ui_scale: float
    total_frames: int
    fps: float
    hits: list[GroundTruthHit]
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "session_id": self.session_id,
            "session_name": self.session_name,
            "description": self.description,
            "resolution": self.resolution,
            "ui_scale": self.ui_scale,
            "total_frames": self.total_frames,
            "fps": self.fps,
            "hits": [hit.to_dict() for hit in self.hits],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BenchmarkAnnotation:
        """Create from dictionary (JSON deserialization)."""
        return cls(
            session_id=data["session_id"],
            session_name=data["session_name"],
            description=data["description"],
            resolution=data["resolution"],
            ui_scale=data["ui_scale"],
            total_frames=data["total_frames"],
            fps=data["fps"],
            hits=[GroundTruthHit.from_dict(hit) for hit in data["hits"]],
            metadata=data.get("metadata"),
        )

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> BenchmarkAnnotation:
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(json_str))

    @classmethod
    def from_file(cls, path: Path | str) -> BenchmarkAnnotation:
        """Load annotation from JSON file."""
        path = Path(path)
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_json(f.read())

    def to_file(self, path: Path | str) -> None:
        """Save annotation to JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())

    def get_hits_for_frame(self, frame: int, tolerance: int = 0) -> list[GroundTruthHit]:
        """Get all ground truth hits for a specific frame.

        Args:
            frame: Frame index to query.
            tolerance: Frame tolerance (e.g., 1 means frame-1 to frame+1).

        Returns:
            List of matching ground truth hits.
        """
        if tolerance == 0:
            return [hit for hit in self.hits if hit.frame == frame]
        return [
            hit for hit in self.hits if abs(hit.frame - frame) <= tolerance
        ]

    @property
    def total_damage(self) -> int:
        """Sum of all damage values in the annotation."""
        return sum(hit.value for hit in self.hits)

    @property
    def hit_count(self) -> int:
        """Total number of annotated hits."""
        return len(self.hits)


class AnnotationBuilder:
    """Builder for creating benchmark annotations programmatically.

    Example:
        annotation = (
            AnnotationBuilder(session_id="session_001")
            .with_metadata(
                session_name="Normal Combat",
                description="Standard combat in zone X",
                resolution="1920x1080",
                ui_scale=100.0,
                total_frames=1000,
                fps=30.0,
            )
            .add_hit(frame=10, value=1234, x=500, y=300)
            .add_hit(frame=15, value=5678, x=520, y=280, damage_type="crit")
            .build()
        )
    """

    def __init__(self, session_id: str) -> None:
        """Initialize builder with session ID.

        Args:
            session_id: Unique identifier for the session.
        """
        self.session_id = session_id
        self.session_name: str = ""
        self.description: str = ""
        self.resolution: str = "1920x1080"
        self.ui_scale: float = 100.0
        self.total_frames: int = 0
        self.fps: float = 30.0
        self.hits: list[GroundTruthHit] = []
        self.metadata: dict[str, Any] = {}

    def with_metadata(
        self,
        session_name: str = "",
        description: str = "",
        resolution: str = "1920x1080",
        ui_scale: float = 100.0,
        total_frames: int = 0,
        fps: float = 30.0,
    ) -> AnnotationBuilder:
        """Set session metadata.

        Args:
            session_name: Human-readable session name.
            description: Session description.
            resolution: Screen resolution as "WIDTHxHEIGHT".
            ui_scale: UI scale percentage.
            total_frames: Total frames in replay.
            fps: Capture frame rate.

        Returns:
            Self for method chaining.
        """
        self.session_name = session_name
        self.description = description
        self.resolution = resolution
        self.ui_scale = ui_scale
        self.total_frames = total_frames
        self.fps = fps
        return self

    def add_hit(
        self,
        frame: int,
        value: int,
        x: float,
        y: float,
        width: int = 0,
        height: int = 0,
        damage_type: str = "direct",
        notes: str = "",
    ) -> AnnotationBuilder:
        """Add a ground truth hit.

        Args:
            frame: Frame index.
            value: Damage value.
            x: X coordinate (relative to damage ROI).
            y: Y coordinate (relative to damage ROI).
            width: Bounding box width.
            height: Bounding box height.
            damage_type: Damage type classification.
            notes: Optional annotation notes.

        Returns:
            Self for method chaining.
        """
        self.hits.append(
            GroundTruthHit(
                frame=frame,
                value=value,
                x=x,
                y=y,
                width=width,
                height=height,
                damage_type=damage_type,
                notes=notes,
            )
        )
        return self

    def add_hits_from_list(
        self,
        hits: list[dict[str, Any]],
    ) -> AnnotationBuilder:
        """Add multiple hits from a list of dictionaries.

        Args:
            hits: List of hit dictionaries with keys matching GroundTruthHit.

        Returns:
            Self for method chaining.
        """
        for hit_data in hits:
            self.add_hit(**hit_data)
        return self

    def with_metadata_dict(self, metadata: dict[str, Any]) -> AnnotationBuilder:
        """Add additional metadata.

        Args:
            metadata: Dictionary of metadata fields.

        Returns:
            Self for method chaining.
        """
        self.metadata.update(metadata)
        return self

    def build(self) -> BenchmarkAnnotation:
        """Build the final annotation.

        Returns:
            Complete BenchmarkAnnotation object.
        """
        return BenchmarkAnnotation(
            session_id=self.session_id,
            session_name=self.session_name,
            description=self.description,
            resolution=self.resolution,
            ui_scale=self.ui_scale,
            total_frames=self.total_frames,
            fps=self.fps,
            hits=self.hits,
            metadata=self.metadata if self.metadata else None,
        )


def load_benchmark_annotations(
    fixtures_dir: Path | str | None = None,
) -> list[BenchmarkAnnotation]:
    """Load all benchmark annotations from fixtures directory.

    Args:
        fixtures_dir: Path to fixtures directory. Defaults to fixtures/benchmarks/.

    Returns:
        List of loaded BenchmarkAnnotation objects.
    """
    if fixtures_dir is None:
        fixtures_dir = Path(__file__).parent.parent.parent.parent / "fixtures" / "benchmarks"
    else:
        fixtures_dir = Path(fixtures_dir)

    if not fixtures_dir.exists():
        return []

    annotations: list[BenchmarkAnnotation] = []
    for path in fixtures_dir.glob("*.json"):
        if path.name.startswith("benchmark_"):
            try:
                annotations.append(BenchmarkAnnotation.from_file(path))
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                print(f"Warning: Failed to load {path}: {e}")

    return annotations


def save_benchmark_annotations(
    annotations: list[BenchmarkAnnotation],
    fixtures_dir: Path | str | None = None,
) -> None:
    """Save benchmark annotations to fixtures directory.

    Args:
        annotations: List of annotations to save.
        fixtures_dir: Path to fixtures directory.
    """
    if fixtures_dir is None:
        fixtures_dir = Path(__file__).parent.parent.parent.parent / "fixtures" / "benchmarks"
    else:
        fixtures_dir = Path(fixtures_dir)

    fixtures_dir.mkdir(parents=True, exist_ok=True)

    for annotation in annotations:
        output_path = fixtures_dir / f"{annotation.session_id}.json"
        annotation.to_file(output_path)
