from d4v.domain.models import StableDamageHit
from d4v.domain.replay_summary import build_replay_combat_summary, infer_duration_ms


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


def test_build_replay_combat_summary_includes_totals_and_top_hits():
    summary = build_replay_combat_summary(
        [
            make_hit(10, 1000, 1200),
            make_hit(20, 2000, 9800),
            make_hit(30, 3000, 500),
        ],
        {"session_name": "round-a", "fps": 10, "frames_written": 40},
        candidate_count=12,
        recognized_count=10,
        parsed_count=8,
        confident_count=6,
    )

    assert summary.session_name == "round-a"
    assert summary.duration_ms == 4000
    assert summary.total_damage == 11500
    assert summary.hit_count == 3
    assert summary.biggest_hit == 9800
    assert summary.top_hits[0].parsed_value == 9800
    assert summary.ocr_coverage.stable_hit_count == 3


def test_infer_duration_ms_falls_back_to_stable_hit_timestamps():
    duration_ms = infer_duration_ms({}, [make_hit(10, 1000, 100), make_hit(50, 5400, 200)])

    assert duration_ms == 5400
