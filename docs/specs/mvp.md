# D4V MVP Spec

## Product Goal

Create a Windows overlay for Diablo IV that shows useful real-time combat stats without modifying the game client.

## User Problem

Players want fast feedback during gameplay:
- how much visible damage they are dealing
- their short-term DPS
- their biggest hit
- how many enemies they have likely killed during the session

## MVP Principles

1. Out-of-process only.
2. Calibrated and honest over flashy and wrong.
3. Damage first, kills second.
4. Every derived metric must have a confidence-aware implementation path.

## MVP Scope

The first shippable version should include:
- Diablo IV window detection
- borderless-window overlay alignment
- configurable combat capture region
- visible damage-number extraction
- temporal deduping for repeated frames
- overlay widgets for:
  - session timer
  - visible damage total
  - rolling 5-second DPS
  - peak hit
  - capture confidence
- reset hotkey
- diagnostics panel with ROI preview
- saved calibration profile per resolution

## Experimental Scope

The following can exist in the codebase during MVP, but must be labeled experimental in the UI:
- estimated kill counter
- automatic combat start/stop detection
- encounter segmentation

## Non-Goals

- exact server-authoritative combat logs
- parsing undocumented game memory for combat events
- build importing, loot filtering, or trading features
- supporting every Diablo IV UI configuration on day one
- cross-platform support

## Functional Requirements

### FR1. Window Binding

The app must detect the active Diablo IV window and update overlay placement when the game window moves or resizes.

### FR2. Capture Pipeline

The app must capture frames from a configurable region at a stable rate suitable for replay and live analysis.

### FR3. Damage Extraction

The app must identify visible damage numbers from captured frames and produce deduped damage events.

### FR4. Session Aggregation

The app must aggregate deduped damage events into:
- session total
- rolling DPS
- peak hit

### FR5. Overlay UX

The overlay must remain readable, lightweight, and always-on-top while avoiding interference with gameplay.

### FR6. Diagnostics

The app must expose a diagnostics mode that shows:
- active ROI
- latest processed frame
- last extracted damage event
- confidence state

## Quality Bar

Before calling the first MVP usable, we should have:
- replay fixtures for at least 3 capture scenarios
- a damage dedupe strategy validated on recorded clips
- manual verification notes for accuracy limits
- a clear unsupported-settings list

## Supported Environment For First Release

- Windows 11
- Diablo IV in borderless windowed mode
- one supported resolution preset to start
- HDR off unless explicitly validated

## Open Product Questions

Questions to answer during prototype validation:
- Are floating damage numbers consistently readable enough for live OCR?
- Can kill inference be good enough to show by default, or should it stay opt-in?
- Which HUD/UI settings materially change detection quality?

## Success Criteria

We consider the MVP successful when:
- the overlay stays aligned during normal gameplay
- visible damage totals are stable enough to feel useful in practice
- peak-hit tracking is trustworthy
- the app can clearly signal when confidence is low

