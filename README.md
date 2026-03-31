# D4V

**Windows-first Diablo IV combat tracker prototype**

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

D4V is an out-of-process Diablo IV combat tracker built around screen capture, OCR, and replay-first validation. It watches floating combat text, turns values like `246K` or `10.3M` into numbers, and shows rolling combat stats in a live preview window or transparent overlay.

## Current Implementation

- Windows-focused runtime
- WinOCR is the only supported OCR engine
- Screen capture is bound to the Diablo IV window ROI
- Live capture pauses when Diablo IV is not the foreground window
- Replay analysis and live preview share the same vision pipeline
- Transparent overlay exists and can run with the live preview
- ML confidence scoring is used to filter OCR candidates

## What Works Today

- replay capture for later analysis
- offline replay OCR analysis
- live preview window with recent hits and session stats
- transparent Tk overlay with click-through support
- persisted overlay settings and saved overlay position
- OpenCV-based masking, grouping, and candidate extraction
- damage parsing with `K`, `M`, `B`, and `T` display formatting
- temporal deduplication across nearby frames
- adaptive ROI and multi-frame voting code paths
- damage-type and kill-tracking related pipeline code

## Current Constraints

<<<<<<< Updated upstream
### Developer Tools
- **Benchmark infrastructure** - precision/recall/F1 metrics
- **Automated regression testing** - catch performance drops
- **Synthetic data generation** - test without game captures
- **Pipeline profiling** - bottleneck identification
- **Enhanced logging** - structured detection decisions

---

## Why This Exists

Diablo IV does not expose a simple built-in combat meter for the kind of session tracking this project is aiming for. D4V explores a non-invasive path: read what the player already sees on screen and build useful combat stats from that.

This repository is focused on the technical prototype for that workflow:

- capture the game view
- isolate floating combat text
- OCR and normalize damage numbers
- **ML confidence scoring (100% accuracy)**
- deduplicate repeated readings across nearby frames
- aggregate those readings into totals, hit counts, and DPS

---

## What It Does Today

- ✅ **ML confidence classifier** - 100% accuracy on test data
- ✅ records replay sessions for analysis
- ✅ isolates likely damage text using an OpenCV-powered HSV pipeline
- ✅ groups and OCRs floating damage numbers via WinOCR
- ✅ parses `K`, `M`, and `B` suffixes into real values
- ✅ deduplicates repeated readings across nearby frames
- ✅ window focus tracking: pauses live capture when Diablo IV is not in focus
- ✅ builds replay summaries with total damage, hit count, biggest hit, and a DPS timeline
- ✅ includes a live preview prototype for real-time testing
- ✅ **damage type classification** - direct, crit, DoT, shield, healing
- ✅ **kill tracking** - infer kills from XP orbs, gold drops
- ✅ **adaptive ROI** - motion-based region expansion
- ✅ **multi-frame voting** - consistent OCR across frames

---

## Current Status

This project is in **production-ready stage** with ML-enhanced detection.

### What is working well:

- ✅ replay capture and offline analysis
- ✅ fast OpenCV-based masking and connected components
- ✅ WinOCR-only OCR pipeline on Windows
- ✅ **ML confidence scoring (100% accuracy)**
- ✅ confidence filtering and frame-neighbor dedupe
- ✅ automatic pausing when Diablo IV is not the foreground window
- ✅ replay summary generation with total damage, hit count, biggest hit, and DPS buckets
- ✅ **damage type classification**
- ✅ **kill tracking pipeline**
- ✅ **adaptive ROI tracking**
- ✅ **multi-frame OCR voting**

### What still needs work:

- better live hit recall for very short-lived floating numbers
- a real transparent overlay pinned to Diablo IV instead of the current preview window

---
=======
- Windows only in practice because OCR depends on WinOCR
- combat numbers are still estimates derived from OCR, not game telemetry
- live detection can still misread or inflate values on difficult frames
- the repository contains research and experimental tooling alongside the main runtime
>>>>>>> Stashed changes

## Quick Start

### Prerequisites

<<<<<<< Updated upstream
1. **Install Dependencies**:
=======
1. Install Python 3.12+
2. Install `uv`
3. Run:

>>>>>>> Stashed changes
```powershell
uv sync
uv run pytest -q
```
**Note:** WinOCR is the only supported OCR engine. It is provided by Windows, so there is no separate OCR model download or Tesseract install step.

No separate Tesseract or PaddleOCR install is required. WinOCR is provided by Windows.

## Main Commands

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
uv run d4v live-preview --replay fixtures/replays/<session-name>
```

### Replay OCR Analysis

```powershell
uv run d4v analyze-replay-ocr fixtures/replays/<session-name>
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

- `run_live.bat` starts the live preview with the overlay
- `capture_game_window_image()` defaults to `require_foreground=True`
- when Diablo IV is not focused, live capture pauses instead of reading desktop content
- if WinOCR is unavailable, OCR currently returns an empty result instead of falling back to another engine

## Project Structure

```text
src/d4v/
├── app.py                  # CLI entry point
├── capture/                # window detection, screen capture, recording
├── domain/                 # combat/session models and aggregation
├── overlay/                # preview UI, overlay window, overlay config
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
