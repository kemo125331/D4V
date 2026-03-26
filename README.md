# D4V

D4V is an experimental Diablo IV combat tracker built around screen capture and OCR.

The goal is to detect floating combat text on screen, turn values like `246k` or `10.3M` into real numbers, and show useful live stats in a lightweight overlay or companion window.

## Why This Exists

Diablo IV does not expose a simple built-in combat meter for the kind of session tracking this project is aiming for. D4V explores a non-invasive path: read what the player already sees on screen and build useful combat stats from that.

This repository is focused on the technical prototype for that workflow:

- capture the game view
- isolate floating combat text
- OCR and normalize damage numbers
- deduplicate repeated readings across nearby frames
- aggregate those readings into totals, hit counts, and DPS

## What It Does Today

- records replay sessions for analysis
- isolates likely damage text using an OpenCV-powered HSV pipeline
- groups and OCRs floating damage numbers via native pytesseract bindings
- parses `K`, `M`, and `B` suffixes into real values
- deduplicates repeated readings across nearby frames
- window focus tracking: pauses live capture when Diablo IV is not in focus
- builds replay summaries with total damage, hit count, biggest hit, and a simple DPS timeline
- includes a live preview prototype for real-time testing

## Current Status

This project is in prototype stage.

Replay analysis is the strongest part right now.

What is working well:

- replay capture and offline analysis
- fast OpenCV-based masking and connected components
- native pytesseract OCR with fallback PSM modes
- confidence filtering and frame-neighbor dedupe
- automatic pausing when Diablo IV is not the foreground window
- replay summary generation with total damage, hit count, biggest hit, and DPS buckets

What still needs work:

- better live hit recall for very short-lived floating numbers
- a real transparent overlay pinned to Diablo IV instead of the current preview window

## Next Milestone

The next important milestone is a trustworthy live prototype.

That means:

1. improve live recall enough to catch most hits in a controlled dummy test
2. promote the current preview panel into a proper overlay shell
3. expand vision to include gold/XP counters using the validated OCR pipeline

Until that lands, replay mode is the best way to evaluate the pipeline.

## Project Structure

- `src/d4v/capture`: frame recording and screen capture helpers
- `src/d4v/vision`: masking, segmentation, grouping, OCR, and parsing
- `src/d4v/domain`: combat models and session aggregation
- `src/d4v/tools`: replay analyzers and live preview entry points
- `src/d4v/overlay`: lightweight preview UI
- `docs`: research, plans, and testing notes

Create the environment and run tests:

1. **Install Tesseract OCR**: This project requires the Tesseract OCR engine installed on your system.
2. **Install Dependencies**:
```powershell
uv sync
uv run pytest -q
```

Replay preview:

```powershell
uv run d4v live-preview --replay fixtures/replays/second-round
```

Live preview:

```powershell
uv run d4v live-preview --live
```

Replay analysis:

```powershell
uv run d4v analyze-replay-ocr fixtures/replays/second-round
```

## Design Principles

- no memory reading or game injection
- vision-first, replay-first validation
- clear iteration from offline analysis to live tracking
- accuracy before overlay polish

## Screenshots

Repository screenshots are not committed yet because the current local captures include active game and desktop content that should be cleaned up before publishing.

Once the live overlay path is more stable, this section should include:

- a clean replay preview screenshot
- a live preview screenshot
- a small pipeline artifact example showing OCR-ready grouped combat text

## Roadmap

- improve Diablo IV window detection for live capture
- raise live hit recall and reduce missed short-lived numbers
- add a real transparent overlay pinned to the game window
- expand from damage stats into kill tracking and encounter summaries

## License

This project is released under the MIT License. See [LICENSE](LICENSE).

## Notes

The repository intentionally focuses on the tracker and analysis pipeline. Large local replay captures and generated artifacts are kept out of version control.
