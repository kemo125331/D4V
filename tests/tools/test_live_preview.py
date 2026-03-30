from pathlib import Path
import threading
import time

from PIL import Image

from d4v.vision.pipeline import DetectedHit
from d4v.tools.live_preview import (
    LivePreviewController,
    ReplayHit,
    ReplayPreviewController,
)


class FakePipeline:
    """Fake pipeline for testing that returns predefined hits."""
    
    def __init__(self, hits_by_frame: dict[int, list[DetectedHit]]) -> None:
        self.hits_by_frame = hits_by_frame
    
    def process_image(self, image: Image.Image, frame_index: int, timestamp_ms: int) -> list[DetectedHit]:
        del image, timestamp_ms
        return self.hits_by_frame.get(frame_index, [])


def test_replay_preview_controller_updates_totals_over_time():
    controller = ReplayPreviewController(
        session_name="round-a",
        duration_ms=2000,
        stable_hits=[
            ReplayHit(frame_index=10, timestamp_ms=500, parsed_value=1000, confidence=1.0),
            ReplayHit(frame_index=20, timestamp_ms=1500, parsed_value=2000, confidence=1.0),
        ],
    )

    controller.start()
    controller.tick(600)

    assert controller.stats.visible_damage_total == 1000
    assert controller.last_hit == 1000

    controller.tick(1000)

    assert controller.stats.visible_damage_total == 3000
    assert controller.stats.hit_count == 2
    assert controller.last_hit == 2000


def test_replay_preview_controller_reset_clears_state():
    controller = ReplayPreviewController(
        session_name="round-a",
        duration_ms=2000,
        stable_hits=[ReplayHit(frame_index=10, timestamp_ms=500, parsed_value=1000, confidence=1.0)],
    )

    controller.start()
    controller.tick(600)
    controller.reset()

    assert controller.stats.visible_damage_total == 0
    assert controller.stats.hit_count == 0
    assert controller.last_hit is None
    assert controller.status == "Ready"


def test_replay_preview_controller_stops_at_end_of_replay():
    controller = ReplayPreviewController(
        session_name="round-a",
        duration_ms=1000,
        stable_hits=[ReplayHit(frame_index=10, timestamp_ms=500, parsed_value=1000, confidence=1.0)],
    )

    controller.start()
    controller.tick(1200)

    assert not controller.is_running
    assert controller.status == "Replay complete"


class FakeRecorder:
    def __init__(self, session_dir: Path) -> None:
        self._session_dir = session_dir
        self.frames_written = 0
        self.is_recording = False

    def start(self, config) -> Path:
        self.is_recording = True
        self._session_dir.mkdir(parents=True, exist_ok=True)
        return self._session_dir

    def stop(self) -> Path:
        self.is_recording = False
        return self._session_dir


def test_live_preview_controller_refreshes_from_analyzer(tmp_path):
    session_dir = tmp_path / "live-a"
    recorder = FakeRecorder(session_dir)

    def analyzer(_session_dir: Path) -> dict[str, object]:
        return {
            "stable_hits": [
                {
                    "frame_index": 5,
                    "timestamp_ms": 500,
                    "parsed_value": 1200,
                    "best_confidence": 1.0,
                },
                {
                    "frame_index": 10,
                    "timestamp_ms": 1000,
                    "parsed_value": 3400,
                    "best_confidence": 1.0,
                },
            ]
        }

    controller = LivePreviewController(
        replay_dir=tmp_path,
        session_name="live-a",
        fps=10,
        refresh_interval_ms=500,
        analyzer=analyzer,
        recorder=recorder,
        background_refresh=False,
    )

    controller.start()
    recorder.frames_written = 12
    controller.tick(600)

    assert controller.stats.visible_damage_total == 4600
    assert controller.stats.hit_count == 2
    assert controller.last_hit == 3400
    assert "12 frames" in controller.status


def test_live_preview_controller_stop_refreshes_one_last_time(tmp_path):
    session_dir = tmp_path / "live-b"
    recorder = FakeRecorder(session_dir)

    def analyzer(_session_dir: Path) -> dict[str, object]:
        return {
            "stable_hits": [
                {
                    "frame_index": 3,
                    "timestamp_ms": 300,
                    "parsed_value": 900,
                    "best_confidence": 0.8,
                }
            ]
        }

    controller = LivePreviewController(
        replay_dir=tmp_path,
        session_name="live-b",
        analyzer=analyzer,
        recorder=recorder,
        background_refresh=False,
    )

    controller.start()
    recorder.frames_written = 5
    controller.stop()

    assert controller.stats.visible_damage_total == 900
    assert controller.status == "Live capture stopped"
    assert not controller.is_running


def test_live_preview_controller_background_refresh_does_not_block_tick(tmp_path):
    session_dir = tmp_path / "live-c"
    recorder = FakeRecorder(session_dir)
    release_event = threading.Event()

    def analyzer(_session_dir: Path) -> dict[str, object]:
        release_event.wait(timeout=2)
        return {
            "stable_hits": [
                {
                    "frame_index": 8,
                    "timestamp_ms": 800,
                    "parsed_value": 1500,
                    "best_confidence": 1.0,
                }
            ]
        }

    controller = LivePreviewController(
        replay_dir=tmp_path,
        session_name="live-c",
        refresh_interval_ms=500,
        analyzer=analyzer,
        recorder=recorder,
        background_refresh=True,
    )

    controller.start()
    recorder.frames_written = 10
    started = time.perf_counter()
    controller.tick(600)
    elapsed = time.perf_counter() - started

    assert elapsed < 0.2
    assert controller.stats.visible_damage_total == 0
    assert "Analyzing live capture" in controller.status

    release_event.set()
    time.sleep(0.05)
    controller.tick(100)

    assert controller.stats.visible_damage_total == 1500


def detect_hits_unused(_frame_path: Path, _fps: int) -> list[DetectedHit]:
    return []


def test_live_preview_controller_streams_new_frames_incrementally(tmp_path):
    session_dir = tmp_path / "live-stream"
    session_dir.mkdir()
    recorder = FakeRecorder(session_dir)

    pipeline = FakePipeline({
        0: [
            DetectedHit(
                frame_index=0,
                timestamp_ms=0,
                parsed_value=1200,
                confidence=1.0,
                sample_text="1.2k",
                center_x=100.0,
                center_y=100.0,
            )
        ],
        1: [
            DetectedHit(
                frame_index=1,
                timestamp_ms=100,
                parsed_value=1200,
                confidence=1.0,
                sample_text="1.2k",
                center_x=102.0,
                center_y=101.0,
            ),
            DetectedHit(
                frame_index=1,
                timestamp_ms=100,
                parsed_value=3400,
                confidence=1.0,
                sample_text="3.4k",
                center_x=200.0,
                center_y=200.0,
            ),
        ],
    })

    def screen_grabber() -> Image.Image:
        return Image.new("RGB", (32, 32), "black")

    controller = LivePreviewController(
        replay_dir=tmp_path,
        session_name="live-stream",
        fps=10,
        pipeline=pipeline,
        screen_grabber=screen_grabber,
        recorder=recorder,
        background_refresh=False,
        require_foreground=False,
    )

    controller.start()
    controller.tick(400)
    controller.tick(400)

    assert controller.stats.visible_damage_total == 4600
    assert controller.stats.hit_count == 2
    assert controller.last_hit == 3400


def test_live_preview_controller_allows_same_value_after_short_gap(tmp_path):
    session_dir = tmp_path / "live-gap"
    session_dir.mkdir()
    recorder = FakeRecorder(session_dir)

    pipeline = FakePipeline({
        0: [
            DetectedHit(
                frame_index=0,
                timestamp_ms=0,
                parsed_value=1200,
                confidence=1.0,
                sample_text="1.2k",
                center_x=100.0,
                center_y=100.0,
            )
        ],
        1: [
            DetectedHit(
                frame_index=1,
                timestamp_ms=100,
                parsed_value=1200,
                confidence=1.0,
                sample_text="1.2k",
                center_x=102.0,
                center_y=101.0,
            )
        ],
        2: [
            DetectedHit(
                frame_index=2,
                timestamp_ms=200,
                parsed_value=1200,
                confidence=1.0,
                sample_text="1.2k",
                center_x=101.0,
                center_y=100.0,
            )
        ],
    })

    def screen_grabber() -> Image.Image:
        return Image.new("RGB", (32, 32), "black")

    controller = LivePreviewController(
        replay_dir=tmp_path,
        session_name="live-gap",
        fps=10,
        pipeline=pipeline,
        screen_grabber=screen_grabber,
        recorder=recorder,
        background_refresh=False,
        require_foreground=False,
    )

    controller.start()
    controller.tick(400)
    controller.tick(400)
    controller.tick(400)

    assert controller.stats.visible_damage_total == 2400
    assert controller.stats.hit_count == 2


def test_live_preview_controller_direct_capture_does_not_wait_for_saved_frames(tmp_path):
    session_dir = tmp_path / "live-direct"
    recorder = FakeRecorder(session_dir)

    pipeline = FakePipeline({
        0: [
            DetectedHit(
                frame_index=0,
                timestamp_ms=0,
                parsed_value=250000,
                confidence=1.0,
                sample_text="250k",
                center_x=140.0,
                center_y=120.0,
            )
        ],
    })

    def screen_grabber() -> Image.Image:
        return Image.new("RGB", (32, 32), "black")

    controller = LivePreviewController(
        replay_dir=tmp_path,
        session_name="live-direct",
        fps=10,
        refresh_interval_ms=300,
        pipeline=pipeline,
        screen_grabber=screen_grabber,
        recorder=recorder,
        background_refresh=False,
        require_foreground=False,
    )

    controller.start()
    controller.tick(400)

    assert controller.stats.visible_damage_total == 250000
    assert controller.stats.hit_count == 1
    assert controller.last_hit == 250000
