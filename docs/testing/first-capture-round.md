# First Damage Capture Round

## Goal

Collect a small set of real Diablo IV samples so we can measure whether visible damage text is readable enough to track reliably.

## What To Record

Please record 3 short clips:

1. Single-target test
- 10 to 15 seconds
- one target or boss-style target
- minimal loot on the ground if possible

2. Dense-pack test
- 10 to 15 seconds
- multiple enemies
- lots of overlapping damage numbers

3. Noise test
- 10 to 15 seconds
- damage numbers mixed with gold pickups and item labels

## Recording Recommendations

- Use borderless windowed mode
- Keep the same resolution for all clips
- Keep the same HUD/font settings for all clips
- If possible record at 60 FPS
- Prefer SDR for the first round
- Do not crop the video before sharing; full game window is better for calibration

## What To Send Alongside The Clips

- resolution
- HUD/font scale
- HDR on or off
- whether loot labels were visible
- whether gold text was visible

## File Format

Best options:
- `mp4`
- extracted `.png` frames in a folder

If you want, place files under:
- `fixtures/replays/<session-name>/`

## What I’ll Analyze First

When you provide the first sample, I’ll check:
- how long damage text survives across frames
- whether raw text is mostly digits or mixed with symbols
- how often gold/item text overlaps the same screen area
- whether a fixed combat ROI is good enough or if we need motion-aware regions

## Current Helper Tool

If we already have OCR candidate output in JSON form, we can summarize it with:

```bash
uv run d4v analyze-candidates path/to/candidates.json
```

To launch the lightweight round helper window:

```bash
uv run d4v capture-round
```

The helper now records full-screen PNG frames directly into:

```text
fixtures/replays/<session-name>/
```

Each run also writes a `metadata.json` file beside the frames.

To analyze a saved replay directory and export combat ROI crops:

```bash
uv run d4v analyze-replay-roi fixtures/replays/second-round
```

To segment likely damage-number tokens from the combat ROI:

```bash
uv run d4v analyze-replay-tokens fixtures/replays/second-round
```

To OCR the top ranked token masks:

```bash
uv run d4v analyze-replay-ocr fixtures/replays/second-round
```

Expected JSON shape:

```json
[
  { "text": "12,500", "frame": 1, "timestamp_ms": 100 },
  { "text": "35 Gold", "frame": 2, "timestamp_ms": 120 }
]
```
