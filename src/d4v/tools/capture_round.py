ROUND_GUIDANCE = """Record 3 short clips:

1. Single-target test
2. Dense-pack test
3. Damage + gold/item noise test

Recommended:
- Borderless windowed mode
- Same resolution and HUD settings for all clips
- Prefer 60 FPS
- Prefer SDR for the first pass
- Do not crop the video

Save samples under:
fixtures/replays/<session-name>/
"""


def main() -> int:
    from d4v.ui.capture_round import run_capture_round

    return run_capture_round()
