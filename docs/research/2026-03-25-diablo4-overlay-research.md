# Diablo IV Combat Overlay Research

Date: 2026-03-25

## Goal

Research whether we can build a Diablo IV overlay that tracks damage and kills, using the following projects as inspiration:
- Diablo4Companion
- d4lf

## Executive Summary

We can confidently build a Diablo IV desktop overlay.

What is not yet proven is the combat-signal layer:
- Overlay rendering is straightforward.
- Window tracking and screen capture are straightforward.
- Accurate live damage and kill extraction is the risky part.

The safest path is a vision-first MVP that estimates visible combat data from captured frames. We should explicitly avoid memory reads, DLL injection, and game-file modification for the first version.

## Reference Project Findings

### 1. Diablo4Companion

Repo:
- https://github.com/josdemmers/Diablo4Companion

What it is:
- A Windows WPF companion app focused on loot filtering, OCR, trading lists, and paragon overlay support.

Key technical observations:
- Targets `.NET 10.0` on Windows with WPF.
- Uses `GameOverlay.Net` for overlay rendering.
- Uses `TesseractOCR` and `Emgu.CV.runtime.windows` for OCR and computer vision.
- Tracks the Diablo IV window and continuously captures the active game window before processing tooltip regions.
- Depends heavily on system presets and per-resolution calibration.

Why it matters to us:
- Good proof that a polished Windows-native overlay is viable.
- Good proof that per-resolution capture calibration is mandatory.
- Not a proof that combat events are easy to read from the game.

### 2. d4lf

Repo:
- https://github.com/d4lfteam/d4lf

Observed current release:
- Latest GitHub release shown on the repo page was `v8.3.2` on 2026-03-23.

What it is:
- A Python desktop utility for loot filtering, item parsing, and paragon overlay workflows.

Key technical observations:
- Uses `mss` for screen capture.
- Uses `opencv-python`, `numpy`, and image-template workflows.
- Uses `PyQt6` for the desktop GUI.
- Uses transparent Tk overlays for some overlay surfaces.
- Tracks the Diablo IV window and works best in borderless windowed mode.
- Uses Diablo IV accessibility/TTS plumbing for item information, but the documented usage is item-focused, not combat-event focused.

Why it matters to us:
- Strong proof that Python is fast enough for an MVP overlay/capture stack.
- Strong proof that out-of-process screen analysis is a practical approach for Diablo IV tooling.
- Not a reusable combat meter implementation.

## What We Can Reuse

Patterns worth borrowing from both projects:
- active-window detection
- borderless-window alignment
- per-resolution calibration profiles
- user-configurable hotkeys
- always-on-top transparent overlay
- replayable screenshot and debug workflows
- strong logging and diagnostics

Patterns we should avoid for MVP:
- any approach that modifies Diablo IV files
- any approach that depends on undocumented process internals
- shipping a complex multi-mode overlay before signal extraction is validated

## Feasibility Analysis For Damage And Kills

### Damage Tracking Options

| Approach | Signal quality | Complexity | Account risk | MVP verdict |
| --- | --- | --- | --- | --- |
| OCR floating damage numbers from screen capture | Medium | Medium to High | Low | Best first option |
| Read combat data from memory/process internals | Potentially high | High | High | Do not use for MVP |
| Use accessibility/TTS as combat feed | Unknown to low | Medium | Medium | Not a primary plan |
| Infer damage from health-bar deltas only | Low to medium | High | Low | Backup experiment only |

### Kill Tracking Options

| Approach | Signal quality | Complexity | Account risk | MVP verdict |
| --- | --- | --- | --- | --- |
| Detect enemy death from health-bar disappearance and recent damage activity | Medium at best | High | Low | Experimental only |
| Count XP/gold pop events as kill proxy | Low to medium | Medium | Low | Weak fallback |
| Read kill state from memory/process internals | Unknown | High | High | Do not use for MVP |

## Most Important Product Insight

This project is not blocked by overlay technology.

It is blocked by measurement fidelity.

That means the first real engineering milestone should be:
- capture footage
- replay footage offline
- prove that we can extract damage events with acceptable error

Until that is done, a large UI build would be premature.

## Proposed MVP Shape

Phase 1 MVP:
- Windows-only desktop app
- bind to the Diablo IV window
- capture frames from a configurable combat ROI
- detect and sum visible floating damage numbers
- show overlay with:
  - session timer
  - visible damage total
  - rolling 5-second DPS
  - peak hit
  - confidence indicator
  - reset hotkey

Phase 1.5:
- add clip recorder and replay validator
- store calibration profiles by resolution and UI scale

Phase 2:
- add experimental kill counter
- label it clearly as estimated until benchmarked

## Recommended Stack

For the first implementation cycle, optimize for experimentation speed:
- Python
- `mss`
- `opencv-python`
- `numpy`
- `PySide6`
- `pytest`

Why not choose a native .NET stack first:
- the highest-risk unknown is the vision pipeline
- Python gives faster iteration for region tuning, preprocessing, and replay tooling
- once the signal layer is trustworthy, we can revisit whether a native Windows overlay is worth the migration cost

## Risk Register

### Risk 1: Damage numbers are too noisy to OCR reliably

Mitigation:
- start with recorded footage
- restrict OCR to digit-only regions
- use temporal deduping so the same number is not counted across multiple frames

### Risk 2: Kill inference is too ambiguous

Mitigation:
- ship damage metrics first
- keep kills behind an explicit experimental label
- validate against manually annotated clips

### Risk 3: UI settings break detection

Mitigation:
- require supported presets
- save calibration by resolution and HUD settings
- expose a diagnostics view with live ROI previews

### Risk 4: ToS or account-safety concerns

Mitigation:
- keep the MVP strictly out-of-process
- avoid memory inspection and game modification
- document the boundary clearly in `agent.md`

## Source Links

- Diablo4Companion repo: https://github.com/josdemmers/Diablo4Companion
- d4lf repo: https://github.com/d4lfteam/d4lf
- Blizzard EULA: https://www.blizzard.com/en-us/legal/08b946df-660a-40e4-a072-1fbde65173b1/blizzard-end-user-license-agreement

## Final Recommendation

Proceed with a Python-based validation-first prototype.

Do not start by building a feature-rich overlay. Start by proving two things:
- we can extract visible damage numbers with acceptable error
- we can keep the overlay aligned and stable while the game window moves or resizes

If those two pieces work, the rest of the product becomes a normal desktop-app problem.

