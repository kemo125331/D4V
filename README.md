# D4V

D4V is an experimental Diablo IV combat tracker built around screen capture and OCR.

The goal is to detect floating combat text on screen, turn values like `246k` or `10.3M` into real numbers, and show useful live stats in a lightweight overlay or companion window.

## What It Does Today

- records replay sessions for analysis
- isolates likely damage text from Diablo IV frames
- groups and OCRs floating damage numbers
- parses `K`, `M`, and `B` suffixes into real values
- deduplicates repeated reads across nearby frames
- builds replay summaries with total damage, hit count, biggest hit, and a simple DPS timeline
- includes a live preview prototype for real-time testing

## Current Status

This project is in prototype stage.

Replay analysis is the strongest part right now. Live detection is improving, but it still needs better game-window targeting before it can be trusted as a real combat meter.

## Project Structure

- `src/d4v/capture`: frame recording and screen capture helpers
- `src/d4v/vision`: masking, segmentation, grouping, OCR, and parsing
- `src/d4v/domain`: combat models and session aggregation
- `src/d4v/tools`: replay analyzers and live preview entry points
- `src/d4v/overlay`: lightweight preview UI
- `docs`: research, plans, and testing notes

## Quick Start

Create the environment and run tests:

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

## Design Principles

- no memory reading or game injection
- vision-first, replay-first validation
- clear iteration from offline analysis to live tracking
- accuracy before overlay polish

## Roadmap

- improve Diablo IV window detection for live capture
- raise live hit recall and reduce missed short-lived numbers
- add a real transparent overlay pinned to the game window
- expand from damage stats into kill tracking and encounter summaries

## Notes

The repository intentionally focuses on the tracker and analysis pipeline. Large local replay captures and generated artifacts are kept out of version control.
