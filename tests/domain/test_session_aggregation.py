from d4v.domain.models import StableDamageHit
from d4v.domain.session_aggregation import aggregate_stable_hits, build_dps_timeline


def make_hit(frame_index: int, timestamp_ms: int, value: int) -> StableDamageHit:
    return StableDamageHit(
        frame_index=frame_index,
        timestamp_ms=timestamp_ms,
        parsed_value=value,
        confidence=1.0,
        sample_text=str(value),
        center_x=0.0,
        center_y=0.0,
        first_frame=frame_index,
        last_frame=frame_index,
        occurrences=1,
    )


def test_aggregate_stable_hits_computes_core_metrics():
    aggregation = aggregate_stable_hits(
        [
            make_hit(10, 1000, 1200),
            make_hit(12, 1200, 9800),
            make_hit(20, 2000, 500),
        ]
    )

    assert aggregation.total_damage == 11500
    assert aggregation.hit_count == 3
    assert aggregation.average_hit == 11500 / 3
    assert aggregation.biggest_hit == 9800


def test_aggregate_stable_hits_handles_empty_input():
    aggregation = aggregate_stable_hits([])

    assert aggregation.total_damage == 0
    assert aggregation.hit_count == 0
    assert aggregation.average_hit == 0.0
    assert aggregation.biggest_hit == 0
    assert aggregation.dps_timeline == []


def test_build_dps_timeline_groups_hits_into_one_second_buckets():
    timeline = build_dps_timeline(
        [
            make_hit(1, 200, 1000),
            make_hit(2, 900, 2000),
            make_hit(3, 1000, 3000),
            make_hit(4, 1800, 4000),
        ],
        bucket_ms=1000,
    )

    assert [(bucket.start_ms, bucket.damage, bucket.hit_count) for bucket in timeline] == [
        (0, 3000, 2),
        (1000, 7000, 2),
    ]
    assert [bucket.dps for bucket in timeline] == [3000.0, 7000.0]
