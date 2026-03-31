# D4V Agent Guide

## Mission

Build a Windows desktop companion for Diablo IV that shows an always-on-top overlay with combat stats.

Current product target:
- visible damage total
- short-window DPS
- peak hit
- estimated kills
- session timer

## Current Stage

This repository is in the research-and-planning phase as of 2026-03-25.
Do not jump straight into implementation choices that assume perfect combat telemetry exists.

## What We Learned From Reference Projects

Reference projects:
- Diablo4Companion: https://github.com/josdemmers/Diablo4Companion
- d4lf: https://github.com/d4lfteam/d4lf
- Diablo-4-XP-and-gold-per-hour (akjroller): https://github.com/akjroller/Diablo-4-XP-and-gold-per-hour
- Aion 2 OCR DPS Meter / PoE 2 OCR Concepts: Proof points that Python+OCR DPS meters are being explored for other modern ARPGs.

Important takeaways:
- Mature Diablo IV tools are out-of-process overlays, not in-game mods.
- They rely on screen capture, OCR, template matching, resolution presets, and window tracking.
- `d4lf` goes further by using Diablo IV accessibility/TTS plumbing for item text, but that does not give us a clean combat-event API.
- `Diablo-4-XP-and-gold-per-hour` proves that Python OCR can successfully parse rapidly updating Diablo 4 UI text (resources), though damage numbers are harder.
- Neither reference project provides a ready-made live damage meter or kill counter pipeline, but other ARPG communities (like Aion 2 and PoE 2) are actively experimenting with Python OCR DPS trackers.

## Hard Constraints

These are project guardrails unless the user explicitly changes direction:

1. Prefer out-of-process capture and overlay techniques.
2. Do not modify Diablo IV files, inject DLLs, read process memory, or hook the game process for MVP work.
3. Treat all combat stats as estimates until validated with replay fixtures.
4. Never label OCR-derived totals as exact server-authoritative damage.
5. Optimize for Windows first.
6. Keep the system usable in borderless windowed mode.
7. Design for per-resolution calibration profiles.

## Recommended Technical Direction

Bias toward a vision-first Python MVP because the biggest unknown is signal quality, not UI polish.

Recommended stack for phase 1:
- Python
- `mss` for capture
- `opencv-python` for image preprocessing and region tracking
- `PySide6` for the desktop shell and overlay
- `numpy` for frame processing
- `pytest` for unit and replay tests

Architecture modules should stay separated so we can swap the overlay or OCR engine later:
- `capture`
- `vision`
- `domain`
- `overlay`
- `storage`
- `app`

## Product Truths We Must Preserve

- Damage tracking is only feasible if the game exposes readable floating numbers or other stable combat UI signals on screen.
- Kill counting is harder than damage summation and may remain experimental longer.
- The first serious milestone is replay-based validation on recorded footage.
- A stable calibration workflow matters as much as the overlay itself.

## Preferred Milestones

1. Build offline replay tooling around recorded clips.
2. Prove visible damage extraction on sample footage.
3. Add a live overlay for validated metrics.
4. Add experimental kill inference with confidence scoring.
5. Only consider lower-level integrations if the user explicitly accepts the risk tradeoff.

## Documentation Rules

When major assumptions change, update:
- `docs/research/`
- `docs/specs/mvp.md`
- `docs/plans/`

If implementation starts, keep docs honest about:
- what is measured
- what is inferred
- what is still experimental

