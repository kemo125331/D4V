from d4v.tools.analyze_replay_ocr import (
    dedupe_hits,
    frame_index_to_timestamp_ms,
    load_replay_metadata,
    render_summary,
    score_ocr_result,
    select_temporal_neighbor_lines,
    values_can_merge,
)


def test_render_summary_includes_counts():
    text = render_summary(
        {
            "replay_summary": {
                "session_name": "round-a",
                "duration_ms": 5000,
                "total_damage": 45600000,
                "hit_count": 1,
                "average_hit": 45600000.0,
                "biggest_hit": 45600000,
                "dps_timeline": [
                    {
                        "start_ms": 0,
                        "end_ms": 1000,
                        "damage": 45600000,
                        "hit_count": 1,
                        "dps": 45600000.0,
                    }
                ],
            },
            "candidate_count": 2,
            "recognized_count": 1,
            "parsed_count": 1,
            "confident_count": 1,
            "stable_hit_count": 1,
                "results": [
                {
                    "mask_name": "a.png",
                    "raw_text": "45.6M",
                    "normalized_text": "45.6M",
                    "parsed_value": 45600000,
                    "confidence": 0.9,
                    "is_plausible": True,
                },
                ],
            "stable_hits": [
                {
                    "frame_index": 10,
                    "timestamp_ms": 1000,
                    "parsed_value": 45600000,
                    "first_frame": 10,
                    "last_frame": 12,
                    "occurrences": 2,
                    "best_confidence": 0.9,
                    "sample_text": "45.6M",
                }
            ],
        }
    )
    assert "Total damage: 45600000" in text
    assert "OCR candidates processed: 2" in text
    assert "parsed=45600000" in text
    assert "Stable deduped hits: 1" in text


def test_score_ocr_result_prefers_parseable_damage_text():
    high = score_ocr_result(
        raw_text="45.6M",
        parsed_value=45_600_000,
        line_score=12.0,
        member_count=4,
        width=80,
        height=30,
    )
    low = score_ocr_result(
        raw_text="M",
        parsed_value=None,
        line_score=12.0,
        member_count=2,
        width=40,
        height=25,
    )
    assert high > low


def test_dedupe_hits_merges_same_value_across_nearby_frames():
    hits = dedupe_hits(
        [
                {
                    "frame_index": 10,
                    "parsed_value": 45_600_000,
                    "confidence": 0.9,
                    "raw_text": "45.6M",
                    "is_plausible": True,
                    "left": 100,
                    "top": 100,
                    "right": 160,
                "bottom": 130,
            },
                {
                    "frame_index": 11,
                    "parsed_value": 45_600_000,
                    "confidence": 0.85,
                    "raw_text": "45.6M",
                    "is_plausible": True,
                    "left": 104,
                    "top": 102,
                    "right": 164,
                "bottom": 132,
            },
        ],
        replay_fps=10,
    )

    assert len(hits) == 1
    assert hits[0].occurrences == 2
    assert hits[0].frame_index == 10
    assert hits[0].timestamp_ms == 1000


def test_dedupe_hits_merges_small_ocr_drift_on_same_track():
    hits = dedupe_hits(
        [
            {
                "frame_index": 77,
                "parsed_value": 905,
                "confidence": 0.8,
                "raw_text": "905",
                "is_plausible": True,
                "left": 100,
                "top": 100,
                "right": 140,
                "bottom": 125,
            },
            {
                "frame_index": 78,
                "parsed_value": 907,
                "confidence": 0.82,
                "raw_text": "907",
                "is_plausible": True,
                "left": 104,
                "top": 103,
                "right": 144,
                "bottom": 128,
            },
        ],
        replay_fps=10,
    )

    assert len(hits) == 1
    assert hits[0].occurrences == 2
    assert hits[0].parsed_value == 907


def test_dedupe_hits_does_not_merge_distinct_large_damage_values():
    hits = dedupe_hits(
        [
            {
                "frame_index": 100,
                "parsed_value": 8_000_000,
                "confidence": 1.0,
                "raw_text": "8M",
                "is_plausible": True,
                "left": 200,
                "top": 120,
                "right": 250,
                "bottom": 150,
            },
            {
                "frame_index": 101,
                "parsed_value": 9_000_000,
                "confidence": 1.0,
                "raw_text": "9M",
                "is_plausible": True,
                "left": 203,
                "top": 121,
                "right": 253,
                "bottom": 151,
            },
        ],
        replay_fps=10,
    )

    assert len(hits) == 2


def test_values_can_merge_uses_tight_tolerance():
    assert values_can_merge(905, 907)
    assert values_can_merge(42_300_000, 42_800_000)
    assert not values_can_merge(8_000_000, 9_000_000)


def test_frame_index_to_timestamp_ms_uses_fps():
    assert frame_index_to_timestamp_ms(12, 10) == 1200
    assert frame_index_to_timestamp_ms(-1, 10) is None
    assert frame_index_to_timestamp_ms(12, 0) is None


def test_load_replay_metadata_reads_json(tmp_path):
    session_dir = tmp_path / "session-a"
    session_dir.mkdir()
    (session_dir / "metadata.json").write_text('{"fps": 10, "session_name": "round-a"}', encoding="utf-8")

    metadata = load_replay_metadata(session_dir)

    assert metadata["fps"] == 10
    assert metadata["session_name"] == "round-a"


def test_select_temporal_neighbor_lines_expands_around_seed_lines():
    seed_lines, selected_lines = select_temporal_neighbor_lines(
        [
            {
                "frame_name": "frame_000010.png",
                "mask_name": "frame_000010/line_000_mask.png",
                "left": 100,
                "top": 100,
                "right": 160,
                "bottom": 130,
                "score": 11.0,
                "is_ocr_ready": True,
            },
            {
                "frame_name": "frame_000011.png",
                "mask_name": "frame_000011/line_000_mask.png",
                "left": 106,
                "top": 102,
                "right": 166,
                "bottom": 132,
                "score": 8.5,
                "is_ocr_ready": True,
            },
            {
                "frame_name": "frame_000012.png",
                "mask_name": "frame_000012/line_000_mask.png",
                "left": 280,
                "top": 240,
                "right": 340,
                "bottom": 270,
                "score": 8.0,
                "is_ocr_ready": True,
            },
            {
                "frame_name": "frame_000020.png",
                "mask_name": "frame_000020/line_000_mask.png",
                "left": 104,
                "top": 100,
                "right": 164,
                "bottom": 130,
                "score": 9.0,
                "is_ocr_ready": True,
            },
        ],
        max_candidates=10,
        seed_count=1,
        frame_window=2,
        center_distance_threshold=25.0,
    )

    assert len(seed_lines) == 1
    assert [line["mask_name"] for line in selected_lines] == [
        "frame_000010/line_000_mask.png",
        "frame_000011/line_000_mask.png",
    ]


def test_select_temporal_neighbor_lines_auto_seed_count_scales():
    lines = []
    for index in range(20):
        lines.append(
            {
                "frame_name": f"frame_{index:06d}.png",
                "mask_name": f"frame_{index:06d}/line_000_mask.png",
                "left": 100 + index,
                "top": 100,
                "right": 150 + index,
                "bottom": 130,
                "score": 10.0,
                "is_ocr_ready": True,
            }
        )

    seed_lines, _selected_lines = select_temporal_neighbor_lines(lines, max_candidates=50)

    assert len(seed_lines) == 12
