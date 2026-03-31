# D4V — Project Context

## Project Overview

**D4V** is an experimental Diablo IV combat tracker built around screen capture and OCR. The project's goal is to detect floating combat text on screen, parse damage values (e.g., `246k`, `10.3M`), and display live stats in a lightweight overlay.

### Key Characteristics

- **Type**: Python desktop application
- **Platform**: Windows 11 (primary target)
- **Stage**: Prototype / Research
- **Core Innovation**: Vision-first, out-of-process combat tracking without game modification

### Design Principles

1. **Out-of-process only** — No memory reading, DLL injection, or game file modification
2. **Vision-first validation** — Replay-based analysis before live overlay polish
3. **Honest over flashy** — Metrics are estimates with confidence indicators
4. **Damage first, kills second** — Prioritize reliable damage tracking before experimental kill counting

---

## Architecture

```
src/d4v/
├── app.py                 # CLI entry point with subcommands
├── capture/               # Screen capture and recording
│   ├── screen_capture.py  # Game window capture via mss
│   ├── recorder.py        # Frame recording to disk
│   └── game_window.py     # Window detection and focus tracking
├── vision/                # Image processing and OCR pipeline
│   ├── color_mask.py      # HSV-based combat text segmentation (OpenCV)
│   ├── segments.py        # Connected components for token isolation
│   ├── grouping.py        # Group nearby tokens into lines
│   ├── ocr.py             # WinOCR-based damage text extraction
│   ├── classifier.py      # Damage text validation and parsing
│   ├── dedupe.py          # Temporal deduplication of repeated readings
│   └── roi.py             # Region-of-interest scaling utilities
├── domain/                # Business logic and data models
│   ├── models.py          # DamageEvent, StableDamageHit, etc.
│   ├── session_stats.py   # Live session aggregation
│   ├── session_aggregation.py  # Replay summary generation
│   └── replay_summary.py  # Replay analysis utilities
├── overlay/               # Desktop UI layer
│   ├── window.py          # PySide6 preview window
│   └── view_model.py      # UI state management
└── tools/                 # CLI utilities
    ├── live_preview.py    # Live and replay preview modes
    ├── analyze_replay_ocr.py  # Offline replay analysis
    └── ...
```

### Technology Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.12+ |
| Capture | `mss` (screen capture) |
| Vision | `opencv-python`, `numpy`, `Pillow` |
| OCR | `winocr` (Windows Runtime OCR) |
| UI | `PySide6` (overlay window) |
| Testing | `pytest` |
| Packaging | `uv`, `hatchling` |

---

## Building and Running

### Prerequisites

1. **Install Python 3.12+**

2. **Install uv** (if not already installed):
   ```powershell
   pip install uv
   ```

### Setup

```powershell
# Install dependencies
uv sync

# Run tests
uv run pytest -q
```

### CLI Commands

```powershell
# Replay preview (offline analysis with UI)
uv run d4v live-preview --replay fixtures/replays/<session-name>

# Live preview (real-time capture)
uv run d4v live-preview --live

# Replay analysis (OCR pipeline on recorded frames)
uv run d4v analyze-replay-ocr fixtures/replays/<session-name>

# Capture a round (record frames for analysis)
uv run d4v capture-round

# Analyze ROI candidates
uv run d4v analyze-replay-roi <session-dir>

# Analyze token candidates
uv run d4v analyze-replay-tokens <session-dir>
```

---

## Development Conventions

### Code Style

- **Type hints**: Use modern Python type hints (`list[str]`, `dict[str, object]`, etc.)
- **Dataclasses**: Prefer `@dataclass(frozen=True)` for immutable domain models
- **Naming**: snake_case for functions/variables, PascalCase for classes
- **Imports**: Group by standard library → third-party → local; use `from __future__ import annotations`

### Testing Practices

- Tests live in `tests/` mirroring `src/d4v/` structure
- Use `pytest` for unit and integration tests
- Smoke test in `tests/test_smoke.py` validates basic imports

### Commit Guidelines

- Clear, concise commit messages focused on "why" over "what"
- Reference related docs in `docs/` when applicable
- Keep commits atomic and focused

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `README.md` | Project overview and quickstart |
| `agent.md` | Agent development guide with milestones and constraints |
| `pyproject.toml` | Dependencies, build config, pytest settings |
| `docs/research/2026-03-25-diablo4-overlay-research.md` | Technical research on reference projects |
| `docs/specs/mvp.md` | MVP specification and requirements |
| `src/d4v/domain/models.py` | Core data models (DamageEvent, StableDamageHit) |
| `src/d4v/vision/ocr.py` | OCR pipeline with WinOCR integration |
| `src/d4v/tools/live_preview.py` | Live and replay preview controllers |

---

## Current Status

### What Works

- ✅ Replay capture and offline analysis
- ✅ OpenCV-based masking and connected components
- ✅ Native WinOCR pipeline for damage-number reading
- ✅ Confidence filtering and frame-neighbor deduplication
- ✅ Automatic pause when Diablo IV loses foreground focus
- ✅ Replay summary generation (total damage, hit count, biggest hit, DPS timeline)
- ✅ Live preview prototype

### Known Limitations

- ⚠️ Live hit recall for very short-lived floating numbers needs improvement
- ⚠️ Transparent overlay pinned to game window not yet implemented
- ⚠️ Kill tracking remains experimental

---

## Related Documentation

- **Research**: `docs/research/` — Analysis of reference projects (Diablo4Companion, d4lf, etc.)
- **Specs**: `docs/specs/mvp.md` — MVP requirements and success criteria
- **Plans**: `docs/plans/` — Implementation roadmaps
- **Testing**: `docs/testing/` — Capture and validation notes
- **Agent Guide**: `agent.md` — Development guidelines and milestones

---

## Notes for AI Assistants

1. **Respect the vision-first approach**: Do not suggest memory-reading or injection-based alternatives unless explicitly asked.

2. **Preserve the out-of-process boundary**: This is a core design principle for ToS compliance and account safety.

3. **Confidence matters**: When suggesting OCR or vision improvements, consider confidence scoring and error handling.

4. **Replay validation**: New vision features should be testable against recorded replay fixtures.

5. **Windows-first**: The project targets Windows 11; avoid cross-platform suggestions that add complexity without benefit.

6. **Documentation updates**: When implementation changes affect assumptions, update relevant docs in `docs/research/`, `docs/specs/`, or `docs/plans/`.
