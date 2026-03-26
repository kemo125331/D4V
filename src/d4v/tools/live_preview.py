from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path
import threading
import time
from typing import Callable

from PIL import Image, ImageOps

from d4v.capture.screen_capture import capture_game_window_image
from d4v.capture.recorder import CaptureSessionConfig, FrameRecorder
from d4v.capture.game_window import is_diablo_iv_foreground
from d4v.domain.models import StableDamageHit
from d4v.domain.session_stats import SessionStats
from d4v.overlay.view_model import PreviewViewModel
from d4v.tools.analyze_replay_ocr import (
    analyze_replay_ocr,
    frame_index_to_timestamp_ms,
    parse_frame_index,
    score_ocr_result,
    values_can_merge,
)
from d4v.tools.analyze_replay_roi import DEFAULT_DAMAGE_ROI
from d4v.tools.analyze_replay_tokens import is_ocr_ready_line, score_line_candidate
from d4v.vision.classifier import is_plausible_damage_text, normalize_damage_text, parse_damage_value
from d4v.vision.color_mask import build_combat_text_mask
from d4v.vision.grouping import GroupedCandidate, group_bounding_boxes
from d4v.vision.ocr import ocr_pil_image
from d4v.vision.roi import scale_relative_roi
from d4v.vision.segments import segment_damage_tokens


@dataclass(frozen=True)
class ReplayHit:
    frame_index: int
    timestamp_ms: int
    parsed_value: int
    confidence: float


@dataclass(frozen=True)
class LiveDetectedHit:
    frame_index: int
    timestamp_ms: int
    parsed_value: int
    confidence: float
    sample_text: str
    center_x: float
    center_y: float


def summary_to_replay_hits(summary: dict[str, object]) -> list[ReplayHit]:
    return [
        ReplayHit(
            frame_index=int(item.get("frame_index", item.get("first_frame", 0))),
            timestamp_ms=int(item.get("timestamp_ms") or 0),
            parsed_value=int(item["parsed_value"]),
            confidence=float(item.get("best_confidence", 0.0)),
        )
        for item in summary.get("stable_hits", [])
    ]


def apply_hits_to_stats(stats: SessionStats, hits: list[ReplayHit]) -> int | None:
    stats.reset()
    last_hit: int | None = None
    for hit in hits:
        stats.add_hit(
            frame=hit.frame_index,
            timestamp_ms=hit.timestamp_ms,
            value=hit.parsed_value,
            confidence=hit.confidence,
        )
        last_hit = hit.parsed_value
    return last_hit


def is_plain_numeric_text(text: str) -> bool:
    if not text:
        return False
    normalized = normalize_damage_text(text)
    return bool(normalized) and normalized[-1:].isdigit() and parse_damage_value(normalized) is not None


def find_adjacent_suffix_hint(
    target_group: GroupedCandidate,
    grouped_candidates: list[GroupedCandidate],
    read_group_text: Callable[[GroupedCandidate], str],
) -> str | None:
    best_hint: str | None = None
    best_gap: int | None = None

    for candidate in grouped_candidates:
        if candidate == target_group:
            continue
        if candidate.left <= target_group.right:
            continue
        if candidate.width > 200 or candidate.height > 120 or candidate.member_count > 6:
            continue

        gap = candidate.left - target_group.right - 1
        if gap > 120:
            continue

        target_center_y = (target_group.top + target_group.bottom) / 2
        candidate_center_y = (candidate.top + candidate.bottom) / 2
        if abs(target_center_y - candidate_center_y) > max(target_group.height, candidate.height) * 0.55:
            continue

        suffix_text = normalize_damage_text(read_group_text(candidate))
        if suffix_text not in {"K", "M", "B"}:
            continue

        if best_gap is None or gap < best_gap:
            best_gap = gap
            best_hint = suffix_text

    return best_hint


def detect_hits_in_frame(
    frame_path: Path,
    fps: int,
    max_line_candidates: int = 18,
) -> list[LiveDetectedHit]:
    frame_index = parse_frame_index(frame_path.name)
    timestamp_ms = frame_index_to_timestamp_ms(frame_index, fps) or 0

    with Image.open(frame_path) as image:
        return detect_hits_in_image(
            image,
            frame_index=frame_index,
            timestamp_ms=timestamp_ms,
            max_line_candidates=max_line_candidates,
        )


def detect_hits_in_image(
    image: Image.Image,
    frame_index: int,
    timestamp_ms: int,
    max_line_candidates: int = 18,
) -> list[LiveDetectedHit]:
    roi = scale_relative_roi(image.size, DEFAULT_DAMAGE_ROI)
    crop = image.crop((roi.left, roi.top, roi.right, roi.bottom)).convert("RGB")
    mask = build_combat_text_mask(crop)
    components = segment_damage_tokens(mask)
    grouped_candidates = group_bounding_boxes(components)

    ranked_lines = sorted(
        (
            grouped
            for grouped in grouped_candidates
            if is_ocr_ready_line(
                grouped.width,
                grouped.height,
                grouped.pixel_count,
                grouped.member_count,
            )
        ),
        key=lambda grouped: score_line_candidate(
            grouped.width,
            grouped.height,
            grouped.pixel_count,
            grouped.member_count,
        ),
        reverse=True,
    )[:max_line_candidates]

    hits: list[LiveDetectedHit] = []
    group_text_cache: dict[tuple[int, int, int, int], str] = {}

    def read_group_text(grouped: GroupedCandidate) -> str:
        key = (grouped.left, grouped.top, grouped.right, grouped.bottom)
        if key in group_text_cache:
            return group_text_cache[key]

        line_mask = mask.crop(
            (
                grouped.left,
                grouped.top,
                grouped.right + 1,
                grouped.bottom + 1,
            )
        )
        expanded_mask = ImageOps.expand(line_mask.convert("L"), border=4, fill=0)
        group_text_cache[key] = ocr_pil_image(expanded_mask)
        return group_text_cache[key]

    for grouped in ranked_lines:
        raw_text = read_group_text(grouped)
        normalized_text = normalize_damage_text(raw_text) if raw_text else ""
        if is_plain_numeric_text(normalized_text):
            suffix_hint = find_adjacent_suffix_hint(grouped, grouped_candidates, read_group_text)
            if suffix_hint is not None:
                raw_text = f"{normalized_text}{suffix_hint}"
                normalized_text = normalize_damage_text(raw_text)
        parsed_value = parse_damage_value(normalized_text) if normalized_text else None
        confidence = score_ocr_result(
            raw_text=normalized_text,
            parsed_value=parsed_value,
            line_score=score_line_candidate(
                grouped.width,
                grouped.height,
                grouped.pixel_count,
                grouped.member_count,
            ),
            member_count=grouped.member_count,
            width=grouped.width,
            height=grouped.height,
        )
        if (
            parsed_value is None
            or confidence < 0.6
            or not is_plausible_damage_text(normalized_text)
        ):
            continue
        hits.append(
            LiveDetectedHit(
                frame_index=frame_index,
                timestamp_ms=timestamp_ms,
                parsed_value=parsed_value,
                confidence=confidence,
                sample_text=raw_text,
                center_x=(grouped.left + grouped.right) / 2,
                center_y=(grouped.top + grouped.bottom) / 2,
            )
        )

    return hits


class ReplayPreviewController:
    window_title = "D4V Replay Preview"
    start_button_label = "Start Replay"

    def __init__(
        self,
        *,
        session_name: str,
        duration_ms: int,
        stable_hits: list[ReplayHit],
    ) -> None:
        self.session_name = session_name
        self.duration_ms = duration_ms
        self.stable_hits = sorted(stable_hits, key=lambda hit: (hit.timestamp_ms, hit.frame_index))
        self.stats = SessionStats()
        self.last_hit: int | None = None
        self.status = "Ready"
        self.elapsed_ms = 0
        self.is_running = False
        self._next_hit_index = 0
        self.hit_log: deque[str] = deque(maxlen=50)

    @classmethod
    def from_session_dir(cls, session_dir: Path) -> "ReplayPreviewController":
        summary = analyze_replay_ocr(session_dir)
        replay_summary = summary.get("replay_summary", {})
        stable_hits = summary_to_replay_hits(summary)
        return cls(
            session_name=str(replay_summary.get("session_name", session_dir.name)),
            duration_ms=int(replay_summary.get("duration_ms", 0)),
            stable_hits=stable_hits,
        )

    def start(self) -> None:
        if self.is_running:
            return
        self.is_running = True
        self.status = "Running replay"

    def stop(self) -> None:
        self.is_running = False
        if self.elapsed_ms >= self.duration_ms and self.duration_ms > 0:
            self.status = "Replay complete"
        else:
            self.status = "Stopped"

    def reset(self) -> None:
        self.stats.reset()
        self.last_hit = None
        self.status = "Ready"
        self.elapsed_ms = 0
        self.is_running = False
        self._next_hit_index = 0
        self.hit_log.clear()

    def tick(self, delta_ms: int) -> None:
        if not self.is_running:
            return

        self.elapsed_ms += delta_ms
        while self._next_hit_index < len(self.stable_hits):
            hit = self.stable_hits[self._next_hit_index]
            if hit.timestamp_ms > self.elapsed_ms:
                break
            self.stats.add_hit(
                frame=hit.frame_index,
                timestamp_ms=hit.timestamp_ms,
                value=hit.parsed_value,
                confidence=hit.confidence,
            )
            self.last_hit = hit.parsed_value
            from d4v.overlay.view_model import format_damage_value
            self.hit_log.append(f"{format_damage_value(hit.parsed_value)}")
            self._next_hit_index += 1

        if self.duration_ms > 0 and self.elapsed_ms >= self.duration_ms:
            self.elapsed_ms = self.duration_ms
            self.stop()
        else:
            self.status = f"Running replay ({self.elapsed_ms}/{self.duration_ms} ms)"

    def view_model(self) -> PreviewViewModel:
        return PreviewViewModel.from_state(
            total_damage=self.stats.visible_damage_total,
            rolling_dps=self.stats.rolling_dps(),
            biggest_hit=self.stats.biggest_hit,
            last_hit=self.last_hit,
            status=self.status,
            recent_hits=list(self.hit_log),
        )


class LivePreviewController:
    window_title = "D4V Live Preview"
    start_button_label = "Start Live"

    def __init__(
        self,
        *,
        replay_dir: Path,
        session_name: str | None = None,
        fps: int = 15,
        refresh_interval_ms: int = 100,
        analyzer: Callable[[Path], dict[str, object]] | None = None,
        frame_processor: Callable[[Path, int], list[LiveDetectedHit]] | None = None,
        screen_grabber: Callable[[], Image.Image | None] | None = None,
        image_processor: Callable[[Image.Image, int, int], list[LiveDetectedHit]] | None = None,
        recorder: FrameRecorder | None = None,
        background_refresh: bool = True,
        require_foreground: bool = True,
    ) -> None:
        self.replay_dir = replay_dir
        self.session_name = session_name or f"live-preview-{time.strftime('%Y%m%d-%H%M%S')}"
        self.fps = fps
        self.refresh_interval_ms = refresh_interval_ms
        self.summary_analyzer = analyzer
        self.frame_processor = frame_processor
        self._using_default_grabber = screen_grabber is None
        self.screen_grabber = screen_grabber or capture_game_window_image
        self.image_processor = image_processor or (
            lambda img, idx, ts: detect_hits_in_image(img, idx, ts, max_line_candidates=16)
        )
        self.recorder = recorder or FrameRecorder(replay_dir)
        self.background_refresh = background_refresh
        self.require_foreground = require_foreground
        self.stats = SessionStats()
        self.last_hit: int | None = None
        self.status = "Ready"
        self.elapsed_ms = 0
        self.is_running = False
        self.session_dir: Path | None = None
        self._last_refresh_ms = 0
        self._last_seen_frames = 0
        self._refresh_lock = threading.Lock()
        self._refresh_thread: threading.Thread | None = None
        self._refresh_in_progress = False
        self._pending_summary: dict[str, object] | None = None
        self._pending_stream_hits: list[LiveDetectedHit] | None = None
        self._pending_frame_count = 0
        self._pending_error: str | None = None
        self._last_processed_frame_index = -1
        self._live_capture_index = 0
        self._recent_detected_hits: deque[LiveDetectedHit] = deque()
        self.hit_log: deque[str] = deque(maxlen=50)

    def start(self) -> None:
        if self.is_running:
            return
        self.session_dir = self.recorder.start(
            CaptureSessionConfig(session_name=self.session_name, fps=self.fps)
        )
        self.is_running = True
        self.elapsed_ms = 0
        self._last_refresh_ms = 0
        self._last_seen_frames = 0
        self._pending_summary = None
        self._pending_stream_hits = None
        self._pending_error = None
        self._live_capture_index = 0
        self.status = f"Live capture started ({self.session_dir.name})"

    def stop(self) -> None:
        self.recorder.stop()
        if not self.background_refresh and self.session_dir is not None:
            self._refresh_from_session(force=True)
        self.is_running = False
        self._apply_pending_refresh()
        self.status = "Live capture stopped"

    def reset(self) -> None:
        if self.is_running:
            self.stop()
        self.stats.reset()
        self.last_hit = None
        self.status = "Ready"
        self.elapsed_ms = 0
        self._last_refresh_ms = 0
        self._last_seen_frames = 0
        self._pending_summary = None
        self._pending_stream_hits = None
        self._pending_error = None
        self._last_processed_frame_index = -1
        self._live_capture_index = 0
        self._recent_detected_hits.clear()
        self.hit_log.clear()

    def tick(self, delta_ms: int) -> None:
        self._apply_pending_refresh()
        if not self.is_running:
            return

        self.elapsed_ms += delta_ms
        if self.session_dir is None:
            self.status = "Live capture error: no session directory"
            return

        if self.summary_analyzer is not None:
            if self.recorder.frames_written <= 0:
                self.status = f"Live capture warming up ({self.elapsed_ms} ms)"
                return

            if (
                self.elapsed_ms - self._last_refresh_ms < self.refresh_interval_ms
                and self.recorder.frames_written == self._last_seen_frames
            ):
                if not self._refresh_in_progress:
                    self.status = f"Live capture ({self.recorder.frames_written} frames)"
                return
        elif self.elapsed_ms - self._last_refresh_ms < self.refresh_interval_ms:
            if not self._refresh_in_progress:
                self.status = (
                    f"Live capture ({self._live_capture_index} samples, "
                    f"{self.stats.hit_count} hits)"
                )
            return

        self._refresh_from_session()

    def _refresh_from_session(self, force: bool = False) -> None:
        if self.session_dir is None:
            return
        frame_count = self.recorder.frames_written if self.summary_analyzer is not None else 0
        if self.summary_analyzer is not None and not force and frame_count <= 0:
            return
        if self._refresh_in_progress:
            if self.summary_analyzer is not None:
                self.status = f"Analyzing live capture ({frame_count} frames)"
            else:
                self.status = f"Analyzing live capture ({self._live_capture_index} samples)"
            return

        if not self.background_refresh:
            self._run_refresh(
                session_dir=self.session_dir,
                frame_count=frame_count,
                use_summary_analyzer=self.summary_analyzer is not None,
            )
            self._apply_pending_refresh()
            return

        self._refresh_in_progress = True
        if self.summary_analyzer is not None:
            self.status = f"Analyzing live capture ({frame_count} frames)"
        else:
            self.status = f"Analyzing live capture ({self._live_capture_index} samples)"
        self._refresh_thread = threading.Thread(
            target=self._run_refresh,
            kwargs={
                "session_dir": self.session_dir,
                "frame_count": frame_count,
                "use_summary_analyzer": self.summary_analyzer is not None,
            },
            name="d4v-live-preview-refresh",
            daemon=True,
        )
        self._refresh_thread.start()

    def _run_refresh(self, *, session_dir: Path, frame_count: int, use_summary_analyzer: bool) -> None:
        try:
            if use_summary_analyzer:
                assert self.summary_analyzer is not None
                summary = self.summary_analyzer(session_dir)
                stream_hits = None
            else:
                summary = None
                stream_hits = self._process_live_capture()
        except FileNotFoundError:
            with self._refresh_lock:
                self._pending_error = "Live capture warming up"
                self._refresh_in_progress = False
            return
        except Exception as exc:
            with self._refresh_lock:
                self._pending_error = f"Live capture error: {exc}"
                self._refresh_in_progress = False
            return

        with self._refresh_lock:
            self._pending_summary = summary
            self._pending_stream_hits = stream_hits
            self._pending_frame_count = frame_count if use_summary_analyzer else self._live_capture_index
            self._refresh_in_progress = False

    def _apply_pending_refresh(self) -> None:
        with self._refresh_lock:
            pending_summary = self._pending_summary
            pending_stream_hits = self._pending_stream_hits
            pending_frame_count = self._pending_frame_count
            pending_error = self._pending_error
            self._pending_summary = None
            self._pending_stream_hits = None
            self._pending_error = None

        if pending_error is not None:
            self.status = pending_error
            return

        applied_hit_count = 0
        if pending_summary is not None:
            hits = summary_to_replay_hits(pending_summary)
            self.last_hit = apply_hits_to_stats(self.stats, hits)
            applied_hit_count = len(hits)
            count_label = "frames"
        elif pending_stream_hits is not None:
            for hit in pending_stream_hits:
                self.stats.add_hit(
                    frame=hit.frame_index,
                    timestamp_ms=hit.timestamp_ms,
                    value=hit.parsed_value,
                    confidence=hit.confidence,
                )
                self.last_hit = hit.parsed_value
                from d4v.overlay.view_model import format_damage_value
                self.hit_log.append(f"{format_damage_value(hit.parsed_value)}")
                self._recent_detected_hits.append(hit)
                applied_hit_count += 1
            self._trim_recent_detected_hits(current_frame_index=self._last_processed_frame_index)
            count_label = "samples"
        else:
            return

        self._last_refresh_ms = self.elapsed_ms
        self._last_seen_frames = pending_frame_count
        self.status = (
            f"Live capture ({pending_frame_count} {count_label}, +{applied_hit_count} hits, "
            f"{self.stats.hit_count} total)"
        )

    def _process_new_frames(self, session_dir: Path) -> list[LiveDetectedHit]:
        new_hits: list[LiveDetectedHit] = []
        recent_hits = deque(self._recent_detected_hits)
        frame_paths = sorted(session_dir.glob("frame_*.png"))
        for frame_path in frame_paths:
            frame_index = parse_frame_index(frame_path.name)
            if frame_index <= self._last_processed_frame_index:
                continue

            processor = self.frame_processor or detect_hits_in_frame
            for hit in processor(frame_path, self.fps):
                if self._is_duplicate_live_hit(hit, recent_hits=recent_hits):
                    continue
                new_hits.append(hit)
                recent_hits.append(hit)

            self._last_processed_frame_index = frame_index
            self._trim_recent_detected_hits(current_frame_index=frame_index, hits=recent_hits)

        return new_hits

    def _process_live_capture(self) -> list[LiveDetectedHit]:
        if self.require_foreground and self._using_default_grabber and not is_diablo_iv_foreground():
            self.status = "Game not in focus — paused"
            return []

        image = self.screen_grabber()
        if image is None:
            # If the game window isn't found, just return an empty hit list
            return []
            
        frame_index = self._live_capture_index
        timestamp_ms = self.elapsed_ms
        self._live_capture_index += 1

        recent_hits = deque(self._recent_detected_hits)
        new_hits: list[LiveDetectedHit] = []
        for hit in self.image_processor(image, frame_index, timestamp_ms):
            if self._is_duplicate_live_hit(hit, recent_hits=recent_hits):
                continue
            new_hits.append(hit)
            recent_hits.append(hit)

        self._last_processed_frame_index = frame_index
        self._trim_recent_detected_hits(current_frame_index=frame_index, hits=recent_hits)
        return new_hits

    def _is_duplicate_live_hit(
        self,
        hit: LiveDetectedHit,
        recent_hits: deque[LiveDetectedHit] | None = None,
        frame_window: int = 1,
        center_distance_threshold: float = 45.0,
    ) -> bool:
        hits = recent_hits if recent_hits is not None else self._recent_detected_hits
        self._trim_recent_detected_hits(
            current_frame_index=hit.frame_index,
            frame_window=frame_window,
            hits=hits,
        )
        for recent_hit in hits:
            if hit.frame_index - recent_hit.frame_index > frame_window:
                continue
            if abs(hit.center_x - recent_hit.center_x) > center_distance_threshold:
                continue
            if abs(hit.center_y - recent_hit.center_y) > center_distance_threshold:
                continue
            if values_can_merge(hit.parsed_value, recent_hit.parsed_value):
                return True
        return False

    def _trim_recent_detected_hits(
        self,
        *,
        current_frame_index: int,
        frame_window: int = 3,
        hits: deque[LiveDetectedHit] | None = None,
    ) -> None:
        target_hits = hits if hits is not None else self._recent_detected_hits
        while target_hits:
            if current_frame_index - target_hits[0].frame_index <= frame_window:
                break
            target_hits.popleft()

    def view_model(self) -> PreviewViewModel:
        return PreviewViewModel.from_state(
            total_damage=self.stats.visible_damage_total,
            rolling_dps=self.stats.rolling_dps(),
            biggest_hit=self.stats.biggest_hit,
            last_hit=self.last_hit,
            status=self.status,
            recent_hits=list(self.hit_log),
        )


def main_replay(session_path: str) -> int:
    from d4v.overlay.window import PreviewWindow

    controller = ReplayPreviewController.from_session_dir(Path(session_path))
    app = PreviewWindow(controller)
    return app.run()


def main_live() -> int:
    from d4v.overlay.window import PreviewWindow

    replay_dir = Path.cwd() / "fixtures" / "replays"
    replay_dir.mkdir(parents=True, exist_ok=True)
    controller = LivePreviewController(replay_dir=replay_dir)
    app = PreviewWindow(controller)
    return app.run()
