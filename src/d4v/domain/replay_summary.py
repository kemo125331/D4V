from __future__ import annotations

from dataclasses import asdict, dataclass

from d4v.domain.models import StableDamageHit
from d4v.domain.session_aggregation import DpsBucket, SessionAggregation, aggregate_stable_hits


@dataclass(frozen=True)
class OcrCoverage:
    candidate_count: int
    recognized_count: int
    parsed_count: int
    confident_count: int
    stable_hit_count: int


@dataclass(frozen=True)
class ReplayCombatSummary:
    session_name: str
    duration_ms: int
    total_damage: int
    hit_count: int
    average_hit: float
    biggest_hit: int
    dps_timeline: list[DpsBucket]
    top_hits: list[StableDamageHit]
    ocr_coverage: OcrCoverage

    def to_dict(self) -> dict[str, object]:
        return {
            "session_name": self.session_name,
            "duration_ms": self.duration_ms,
            "total_damage": self.total_damage,
            "hit_count": self.hit_count,
            "average_hit": self.average_hit,
            "biggest_hit": self.biggest_hit,
            "dps_timeline": [asdict(bucket) for bucket in self.dps_timeline],
            "top_hits": [asdict(hit) for hit in self.top_hits],
            "ocr_coverage": asdict(self.ocr_coverage),
        }


def build_replay_combat_summary(
    stable_hits: list[StableDamageHit],
    metadata: dict[str, object],
    *,
    candidate_count: int,
    recognized_count: int,
    parsed_count: int,
    confident_count: int,
) -> ReplayCombatSummary:
    aggregation = aggregate_stable_hits(stable_hits)
    duration_ms = infer_duration_ms(metadata, stable_hits)
    session_name = str(metadata.get("session_name", "unknown-session"))

    return ReplayCombatSummary(
        session_name=session_name,
        duration_ms=duration_ms,
        total_damage=aggregation.total_damage,
        hit_count=aggregation.hit_count,
        average_hit=aggregation.average_hit,
        biggest_hit=aggregation.biggest_hit,
        dps_timeline=aggregation.dps_timeline,
        top_hits=sorted(
            stable_hits,
            key=lambda hit: (-hit.parsed_value, hit.frame_index),
        )[:5],
        ocr_coverage=OcrCoverage(
            candidate_count=candidate_count,
            recognized_count=recognized_count,
            parsed_count=parsed_count,
            confident_count=confident_count,
            stable_hit_count=len(stable_hits),
        ),
    )


def infer_duration_ms(metadata: dict[str, object], stable_hits: list[StableDamageHit]) -> int:
    fps = metadata.get("fps")
    frames_written = metadata.get("frames_written")
    if isinstance(fps, (int, float)) and fps > 0 and isinstance(frames_written, int):
        return int(round((frames_written / fps) * 1000))

    if stable_hits:
        return max(hit.timestamp_ms or 0 for hit in stable_hits)

    return 0
