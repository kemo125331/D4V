# D4V

**Windows-first Diablo IV combat tracker prototype**

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

D4V is an out-of-process Diablo IV combat tracker built around screen capture, OCR, and replay-first validation. It watches floating combat text, turns values like `246K` or `10.3M` into numbers, and shows rolling combat stats in a Qt desktop shell or transparent overlay.

## Current Implementation

- Windows-focused runtime
- WinOCR is the only supported OCR engine
- Screen capture is bound to the Diablo IV window ROI
- Live capture pauses when Diablo IV is not the foreground window
- Replay analysis and live preview share the same vision pipeline
- Transparent Qt overlay exists and can run with the live preview
- ML confidence scoring is used to filter OCR candidates

## What Works Today

- replay capture for later analysis
- offline replay OCR analysis
- Qt desktop shell with compact session stats
- transparent Qt overlay with click-through support
- persisted overlay settings and saved overlay position
- OpenCV-based masking, grouping, and candidate extraction
- damage parsing with `K`, `M`, `B`, and `T` display formatting
- temporal deduplication across nearby frames
- adaptive ROI and multi-frame voting code paths
- damage-type and kill-tracking related pipeline code

## Current Constraints

- Windows only in practice because OCR depends on WinOCR
- combat numbers are still estimates derived from OCR, not game telemetry
- live detection can still misread or inflate values on difficult frames
- the repository contains research and experimental tooling alongside the main runtime

## Quick Start

### Prerequisites

1. Install Python 3.12+
2. Install `uv`
3. Run:

```powershell
uv sync
uv run pytest -q
```

No separate Tesseract or PaddleOCR install is required. WinOCR is provided by Windows.

## Main Commands

### Desktop App

```powershell
uv run d4v-desktop
```

### Live Preview

```powershell
uv run d4v live-preview --live
```

### Live Preview With Overlay

```powershell
uv run d4v live-preview --with-overlay
```

### Replay Preview

```powershell
uv run d4v live-preview --replay %APPDATA%\D4V\replays\<session-name>
```

### Replay OCR Analysis

```powershell
uv run d4v analyze-replay-ocr %APPDATA%\D4V\replays\<session-name>
```

### Capture A Session

```powershell
uv run d4v capture-round
```

### Overlay Only

```powershell
uv run d4v game-overlay
```

## Runtime Notes

- `d4v-desktop` is the normal-user launch path
- `capture_game_window_image()` defaults to `require_foreground=True`
- when Diablo IV is not focused, live capture pauses instead of reading desktop content
- if WinOCR is unavailable, OCR currently returns an empty result instead of falling back to another engine
- live captures and recorded replay sessions are stored under `%APPDATA%\D4V\replays`

## Windows Build

For a normal-user standalone `.exe`, build on Windows with:

```powershell
./scripts/build_windows.ps1
```

This produces `dist/D4V.exe`, a double-clickable desktop build that launches the Qt desktop shell with overlay support.

GitHub Actions also builds the Windows executable in `.github/workflows/build-windows.yml` and uploads `D4V-windows-x64.zip` as a workflow artifact.

## Project Structure

```text
src/d4v/
├── app.py                  # CLI entry point
├── capture/                # window detection, screen capture, recording
├── domain/                 # combat/session models and aggregation
├── overlay/                # overlay config and shared overlay view models
├── ui/                     # Qt shell, capture assistant, live overlay runtime
├── tools/                  # live preview and replay analysis commands
└── vision/                 # masking, grouping, OCR, ML scoring
```

## Development Status

This is still a prototype, not a production-finished tracker.

The codebase currently has:

- a working WinOCR-only OCR path
- a working overlay path integrated with live preview
- a passing automated test suite on the merged codebase
- ongoing accuracy and recall work for hard combat frames

## Design Principles

- no memory reading or injection
- replay-first validation
- keep OCR-derived stats clearly separate from authoritative game data
- prefer small, testable iterations over large speculative changes

## Documentation

- `docs/DEPLOYMENT_COMPLETE.md`
- `docs/TRAINING_SUMMARY.md`
- `docs/training-results.md`
- `docs/batch-processing-guide.md`
- `docs/GAME_OVERLAY.md`
- `docs/plans/detection-improvements-final.md`

## License

MIT
