"""4-minute live debug session using the actual LivePreviewController."""

import time
from pathlib import Path

from d4v.tools.live_preview import LivePreviewController
from d4v.capture.game_window import is_diablo_iv_foreground


def main():
    replay_dir = Path.cwd() / "fixtures" / "replays"
    replay_dir.mkdir(parents=True, exist_ok=True)

    controller = LivePreviewController(
        replay_dir=replay_dir,
        require_foreground=True,
    )

    print("=" * 60)
    print("  D4V Live Preview — 4-Minute Debug Session")
    print("=" * 60)
    print(f"  Start:  {time.strftime('%H:%M:%S')}")
    print(f"  Duration: 240s (4 minutes)")
    print(f"  OCR:    WinOCR only")
    print(f"  Mode:   LivePreviewController (no GUI)")
    print("=" * 60)
    print()

    controller.start()
    start = time.time()
    duration = 240
    tick_interval = 0.1  # 100ms ticks (matching refresh_interval_ms)
    last_status_log = 0

    try:
        while (time.time() - start) < duration:
            elapsed = time.time() - start
            delta_ms = int((time.time() - start - (elapsed - tick_interval)) * 1000)
            controller.tick(delta_ms)

            # Log status every 30 seconds
            if elapsed - last_status_log >= 30:
                last_status_log = elapsed
                vm = controller.view_model()
                focus = is_diablo_iv_foreground()
                print(
                    f"[{elapsed:.0f}s] Samples={controller._live_capture_index}, "
                    f"Hits={controller.stats.hit_count}, "
                    f"Total DMG={controller.stats.visible_damage_total:,}, "
                    f"Rolling DPS={controller.stats.rolling_dps():,.0f}, "
                    f"Focus={focus}"
                )
                if controller.hit_log:
                    print(f"  Recent hits: {', '.join(list(controller.hit_log)[-5:])}")

            time.sleep(tick_interval)

    finally:
        controller.stop()

    print()
    print("=" * 60)
    print("  Session Complete")
    print("=" * 60)
    vm = controller.view_model()
    print(f"  Total samples:  {controller._live_capture_index}")
    print(f"  Total hits:     {controller.stats.hit_count}")
    print(f"  Total damage:   {controller.stats.visible_damage_total:,}")
    print(f"  Biggest hit:    {controller.stats.biggest_hit:,}")
    print(f"  Avg hit:        {controller.stats.average_hit:,}")
    print(f"  Rolling DPS:    {controller.stats.rolling_dps():,.0f}")
    print(f"  Duration:       {time.time() - start:.0f}s")
    print()
    if controller.hit_log:
        print("  Last 10 hits:")
        for entry in list(controller.hit_log)[-10:]:
            print(f"    {entry}")
    else:
        print("  No hits detected during session.")
    print()
    print(f"  Status: {controller.status}")
    if controller.session_dir:
        print(f"  Session dir: {controller.session_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
