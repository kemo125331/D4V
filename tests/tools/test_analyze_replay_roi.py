from pathlib import Path

from PIL import Image

from d4v.tools.analyze_replay_roi import analyze_session_roi


def test_analyze_session_roi_writes_summary_and_preview(tmp_path):
    session_dir = tmp_path / "session-a"
    session_dir.mkdir()

    frame = Image.new("RGB", (100, 100), color=(0, 0, 0))
    frame.putpixel((50, 50), (240, 210, 90))
    frame.save(session_dir / "frame_000000.png")

    summary = analyze_session_roi(session_dir, relative_roi=(0.4, 0.4, 0.2, 0.2))

    output_dir = session_dir / "analysis" / "combat-roi"
    assert summary["frame_count"] == 1
    assert (output_dir / "summary.json").exists()
    assert (output_dir / "roi-preview.png").exists()
    assert (output_dir / "contact-sheet.png").exists()
