"""Live debug session - runs for 4 minutes and reports all detections."""

import time
from pathlib import Path

from d4v.capture.screen_capture import capture_game_window_image
from d4v.vision.pipeline import CombatTextPipeline
from d4v.vision.config import VisionConfig
from d4v.capture.game_window import is_diablo_iv_foreground


def main():
    pipeline = CombatTextPipeline(VisionConfig())
    frame_count = 0
    hit_count = 0
    total_time = 0.0
    start = time.time()
    duration = 240  # 4 minutes

    print("=" * 60)
    print("  D4V Live Debug Session")
    print("=" * 60)
    print(f"  Start:  {time.strftime('%H:%M:%S')}")
    print(f"  Duration: {duration}s (4 minutes)")
    print(f"  OCR:    WinOCR only")
    print("=" * 60)
    print()

    last_hit_log: list[str] = []

    while (time.time() - start) < duration:
        frame_count += 1
        frame_start = time.time()

        in_focus = is_diablo_iv_foreground()
        img = capture_game_window_image()

        if img is None:
            if frame_count % 60 == 0:
                elapsed = time.time() - start
                print(
                    f"[{elapsed:.0f}s] Frame {frame_count}: No capture (game not found or not in focus)"
                )
            time.sleep(0.5)
            continue

        hits = pipeline.process_image(
            img, frame_count, int((time.time() - start) * 1000)
        )

        frame_time = (time.time() - frame_start) * 1000
        total_time += frame_time

        if hits:
            hit_count += len(hits)
            for hit in hits:
                log_entry = f'[{time.time() - start:.1f}s] HIT: {hit.parsed_value:,} (conf={hit.confidence:.2f}, text="{hit.sample_text}")'
                print(log_entry)
                last_hit_log.append(log_entry)

        if frame_count % 30 == 0:
            avg_time = total_time / frame_count
            fps = 1000.0 / avg_time if avg_time > 0 else 0
            print(
                f"[{time.time() - start:.0f}s] Frame {frame_count}: {frame_time:.0f}ms (avg {avg_time:.0f}ms, ~{fps:.1f} fps), focus={in_focus}, hits_this_frame={len(hits)}, total_hits={hit_count}"
            )

        time.sleep(0.1)

    print()
    print("=" * 60)
    print("  Session Complete")
    print("=" * 60)
    print(f"  Total frames:   {frame_count}")
    print(f"  Total hits:     {hit_count}")
    if frame_count > 0 and total_time > 0:
        print(f"  Avg frame time: {total_time / frame_count:.0f}ms")
        print(f"  Avg FPS:        {1000.0 / (total_time / frame_count):.1f}")
    else:
        print(f"  Avg frame time: N/A (no captures)")
        print(f"  Avg FPS:        N/A")
    print(f"  Duration:       {time.time() - start:.0f}s")
    print()
    if last_hit_log:
        print("  Last 10 hits:")
        for entry in last_hit_log[-10:]:
            print(f"    {entry}")
    else:
        print("  No hits detected during session.")
    print("=" * 60)


if __name__ == "__main__":
    main()
