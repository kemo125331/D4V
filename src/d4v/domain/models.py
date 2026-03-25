from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True)
class DamageEvent:
    frame: int
    value: int
    timestamp_ms: int | None = None
    confidence: float = 0.0


@dataclass
class StableDamageHit:
    frame_index: int
    parsed_value: int
    timestamp_ms: int | None = None
    confidence: float = 0.0
    sample_text: str = ""
    center_x: float = 0.0
    center_y: float = 0.0
    first_frame: int = 0
    last_frame: int = 0
    occurrences: int = 1


class FloatingTextKind(StrEnum):
    DAMAGE = "damage"
    GOLD = "gold"
    ITEM = "item"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class FloatingTextCandidate:
    text: str
    frame: int
    timestamp_ms: int | None = None
    confidence: float = 0.0
    kind: FloatingTextKind = FloatingTextKind.UNKNOWN
