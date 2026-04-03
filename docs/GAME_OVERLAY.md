# Qt Overlay Documentation

## Overview

The D4V overlay is a transparent, always-on-top Qt window that shows combat stats in the bottom-left corner of your Diablo IV window.

## What It Shows

- `AVG DMG`
- `LAST DMG`
- `DPS`
- `PEAK`
- `TOTAL`
- `HITS`

## Usage

### Overlay Only

```powershell
uv run d4v game-overlay
```

### Live Preview With Overlay

```powershell
uv run d4v live-preview --with-overlay
```

### Live Preview Only

```powershell
uv run d4v live-preview --live
```

## Behavior

- Click-through is configurable from the desktop shell.
- Position is saved automatically when you drag the overlay.
- Reset Position returns the overlay to auto-follow mode.
- Replay mode uses the same shared view model, but hides the overlay controls in the shell.

## Implementation Notes

- `src/d4v/ui/overlay.py` contains the Qt overlay window.
- `src/d4v/ui/overlay_runtime.py` contains the standalone overlay launcher.
- `src/d4v/overlay/game_overlay.py` contains the shared controller and formatting helpers.

## Requirements

- Windows 11 for the window-positioning APIs
- Diablo IV running for auto-positioning
- Python 3.12+ for source runs, or the packaged `D4V.exe` for normal use

## Troubleshooting

- If the overlay does not appear, confirm Diablo IV is running and focused.
- If the overlay stops following the game window, click `Reset Position`.
- If the overlay looks too dense, switch the shell overlay mode to `compact`.
