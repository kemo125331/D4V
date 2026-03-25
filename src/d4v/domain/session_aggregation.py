from __future__ import annotations

from dataclasses import dataclass

from d4v.domain.models import StableDamageHit


@dataclass(frozen=True)
class DpsBucket:
    start_ms: int
    end_ms: int
    damage: int
    hit_count: int
    dps: float


@dataclass(frozen=True)
class SessionAggregation:
    total_damage: int
    hit_count: int
    average_hit: float
    biggest_hit: int
    dps_timeline: list[DpsBucket]


def aggregate_stable_hits(
    stable_hits: list[StableDamageHit],
    bucket_ms: int = 1000,
) -> SessionAggregation:
    if not stable_hits:
        return SessionAggregation(
            total_damage=0,
            hit_count=0,
            average_hit=0.0,
            biggest_hit=0,
            dps_timeline=[],
        )

    total_damage = sum(hit.parsed_value for hit in stable_hits)
    hit_count = len(stable_hits)
    biggest_hit = max(hit.parsed_value for hit in stable_hits)

    return SessionAggregation(
        total_damage=total_damage,
        hit_count=hit_count,
        average_hit=total_damage / hit_count,
        biggest_hit=biggest_hit,
        dps_timeline=build_dps_timeline(stable_hits, bucket_ms=bucket_ms),
    )


def build_dps_timeline(
    stable_hits: list[StableDamageHit],
    bucket_ms: int = 1000,
) -> list[DpsBucket]:
    if not stable_hits:
        return []

    bucket_totals: dict[int, int] = {}
    bucket_counts: dict[int, int] = {}

    for hit in stable_hits:
        timestamp_ms = hit.timestamp_ms if hit.timestamp_ms is not None else hit.frame_index
        bucket_index = max(timestamp_ms, 0) // bucket_ms
        bucket_totals[bucket_index] = bucket_totals.get(bucket_index, 0) + hit.parsed_value
        bucket_counts[bucket_index] = bucket_counts.get(bucket_index, 0) + 1

    max_bucket_index = max(bucket_totals)
    timeline: list[DpsBucket] = []
    for bucket_index in range(max_bucket_index + 1):
        damage = bucket_totals.get(bucket_index, 0)
        hit_count = bucket_counts.get(bucket_index, 0)
        start_ms = bucket_index * bucket_ms
        end_ms = start_ms + bucket_ms
        timeline.append(
            DpsBucket(
                start_ms=start_ms,
                end_ms=end_ms,
                damage=damage,
                hit_count=hit_count,
                dps=damage / (bucket_ms / 1000),
            )
        )

    return timeline
