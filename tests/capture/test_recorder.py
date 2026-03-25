from pathlib import Path

from d4v.capture.recorder import CaptureSessionConfig, FrameRecorder


def test_recorder_start_prepares_session_directory(tmp_path):
    recorder = FrameRecorder(tmp_path)

    session_dir = recorder.start(CaptureSessionConfig(session_name="round-a", fps=1))
    recorder.stop()

    assert session_dir == tmp_path / "round-a"
    assert session_dir.exists()
    assert (session_dir / "metadata.json").exists()
