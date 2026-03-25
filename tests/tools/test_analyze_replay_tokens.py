from PIL import Image

from d4v.tools.analyze_replay_tokens import (
    extract_replay_tokens,
    is_ocr_ready_candidate,
    recommend_top_frame_count,
    select_frame_paths_for_segmentation,
    score_token_candidate,
)


def test_extract_replay_tokens_writes_token_summary(tmp_path):
    session_dir = tmp_path / "session-b"
    session_dir.mkdir()

    frame = Image.new("RGB", (100, 100), color=(0, 0, 0))
    for x in range(40, 46):
        for y in range(40, 55):
            frame.putpixel((x, y), (240, 210, 90))
    for x in range(48, 53):
        for y in range(40, 55):
            frame.putpixel((x, y), (240, 210, 90))
    frame.save(session_dir / "frame_000000.png")

    summary = extract_replay_tokens(session_dir, relative_roi=(0.3, 0.3, 0.4, 0.4), top_frame_count=1)

    output_dir = session_dir / "analysis" / "combat-tokens"
    line_output_dir = session_dir / "analysis" / "combat-lines"
    assert summary["token_count"] >= 1
    assert summary["line_count"] >= 1
    assert (output_dir / "summary.json").exists()
    assert line_output_dir.exists()


def test_extract_replay_tokens_can_limit_to_recent_frames(tmp_path):
    session_dir = tmp_path / "session-c"
    session_dir.mkdir()

    old_frame = Image.new("RGB", (100, 100), color=(0, 0, 0))
    old_frame.putpixel((10, 10), (240, 210, 90))
    old_frame.save(session_dir / "frame_000000.png")

    recent_frame = Image.new("RGB", (100, 100), color=(0, 0, 0))
    for x in range(40, 46):
        for y in range(40, 55):
            recent_frame.putpixel((x, y), (240, 210, 90))
    for x in range(48, 53):
        for y in range(40, 55):
            recent_frame.putpixel((x, y), (240, 210, 90))
    recent_frame.save(session_dir / "frame_000001.png")

    summary = extract_replay_tokens(
        session_dir,
        relative_roi=(0.3, 0.3, 0.4, 0.4),
        top_frame_count=1,
        recent_frame_limit=1,
    )

    assert summary["frame_count"] == 1
    assert summary["top_frames"][0]["frame_name"] == "frame_000001.png"


def test_score_token_candidate_prefers_medium_clean_tokens():
    clean_score = score_token_candidate(width=40, height=24, pixel_count=260)
    blob_score = score_token_candidate(width=260, height=150, pixel_count=18000)
    assert clean_score > blob_score


def test_is_ocr_ready_candidate_rejects_large_blob():
    assert is_ocr_ready_candidate(width=40, height=24, pixel_count=260)
    assert not is_ocr_ready_candidate(width=260, height=150, pixel_count=18000)


def test_select_frame_paths_for_segmentation_includes_neighbors(tmp_path):
    scored_frames = [
        (tmp_path / "frame_000000.png", 20),
        (tmp_path / "frame_000001.png", 100),
        (tmp_path / "frame_000002.png", 30),
        (tmp_path / "frame_000003.png", 90),
        (tmp_path / "frame_000004.png", 10),
    ]

    seed_frames, selected_frames = select_frame_paths_for_segmentation(
        scored_frames,
        top_frame_count=1,
        neighbor_radius=1,
    )

    assert [path.name for path, _score in seed_frames] == ["frame_000001.png"]
    assert [path.name for path, _score in selected_frames] == [
        "frame_000000.png",
        "frame_000001.png",
        "frame_000002.png",
    ]


def test_recommend_top_frame_count_scales_with_session_size():
    assert recommend_top_frame_count(0) == 6
    assert recommend_top_frame_count(30) == 6
    assert recommend_top_frame_count(120) == 14
    assert recommend_top_frame_count(400) == 30
