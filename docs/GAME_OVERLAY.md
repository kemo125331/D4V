# Game Overlay Documentation

## Overview

The D4V Game Overlay is a transparent, always-on-top window that displays combat statistics in the bottom-left corner of your Diablo IV game window.

## Features

- **Transparent Background**: Semi-transparent dark theme that doesn't obstruct gameplay
- **Auto-Positioning**: Automatically positions at bottom-left of Diablo IV window
- **Real-time Stats**: Updates every 100ms with live combat data
- **Key Metrics Displayed**:
  - **AVG DMG** (green, large): Average damage per hit
  - **LAST DMG** (yellow, large): Most recent damage value
  - **DPS** (white, small): Rolling damage per second (5-second window)
  - **TOTAL** (white, small): Total damage dealt
  - **HITS** (white, small): Number of hits detected

## Usage

### Option 1: Game Overlay Only (Standalone)

Run the overlay without the preview window:

```powershell
# Using CLI
uv run d4v game-overlay

# Or using batch file
.\run_overlay.bat
# Then choose option 1
```

### Option 2: Live Preview + Game Overlay (Combined)

Run both the preview window and game overlay together:

```powershell
# Using CLI
uv run d4v live-preview --with-overlay

# Or using batch file
.\run_overlay.bat
# Then choose option 2
```

### Option 3: Preview Window Only

Run just the preview window (original behavior):

```powershell
# Using CLI
uv run d4v live-preview --live

# Note: run_live.bat starts the combined preview + overlay mode
```

## Architecture

### Files Created

| File | Purpose |
|------|---------|
| `src/d4v/overlay/game_overlay.py` | Main overlay implementation |
| `run_overlay.bat` | Quick-launch batch file |

### Components

- **GameOverlayWindow**: Tkinter-based transparent window
- **GameOverlayController**: Controller managing stats and state
- **GameOverlayViewModel**: View model for formatting display values

### Integration

The overlay can:
1. Run standalone with its own `SessionStats`
2. Share `SessionStats` with `LivePreviewController` when using `--with-overlay`

## Visual Design

```
┌─────────────────────────┐
│ D4V Combat              │  ← Header (gray)
├─────────────────────────┤
│ AVG DMG    125,430      │  ← Green, large
│ LAST DMG   89,200       │  ← Yellow, large
├─────────────────────────┤
│ DPS        45,230       │  ← White, small
│ TOTAL      1,234,567    │  ← White, small
│ HITS       42           │  ← White, small
└─────────────────────────┘
```

## Technical Details

### Window Properties

- **Style**: Borderless, click-through capable
- **Background**: Semi-transparent dark (#1a1a1a)
- **Position**: Bottom-left of Diablo IV window (+20px offset)
- **Size**: Auto-sized based on content (~200px tall)
- **Always on Top**: Yes (stays above game window)

### Positioning Logic

1. Detects Diablo IV window bounds using Windows API
2. Positions at `(left + 20, bottom - 200)`
3. Falls back to screen bottom-left if D4 window not found

### Update Loop

- Runs at 100ms intervals (10 updates/second)
- Re-positions on each update (tracks window movement)
- Updates stats from shared `SessionStats` object

## Requirements

- Windows 11 (for window positioning APIs)
- Diablo IV running (for auto-positioning)
- Python 3.12+
- Tkinter (included with Python)

## Troubleshooting

### Overlay not appearing

1. Ensure Diablo IV is running
2. Check if overlay is positioned off-screen
3. Try running as administrator

### Overlay not updating

1. Verify live capture is running (if using `--with-overlay`)
2. Check that damage numbers are being detected
3. Review ML model status in preview window

### Overlay in wrong position

1. The overlay auto-updates position every 100ms
2. If Diablo IV window moves, overlay should follow
3. Restart overlay if position becomes stale

## Future Enhancements

Potential improvements:
- [ ] Additional stats (crit rate, hit frequency)
- [ ] Configurable update rate
- [ ] Multiple overlay themes
- [ ] Minimize to system tray

## API Reference

### GameOverlayWindow

```python
# Create and run overlay
from d4v.overlay.game_overlay import GameOverlayWindow, GameOverlayController

controller = GameOverlayController()
app = GameOverlayWindow(controller)
app.run()
```

### GameOverlayController

```python
# Add a hit manually
controller.add_hit(value=123456)

# Start/stop/reset
controller.start()
controller.stop()
controller.reset()

# Get current view model
view_model = controller.view_model()
```

### CLI Commands

```bash
# Standalone overlay
d4v game-overlay

# Live preview with overlay
d4v live-preview --with-overlay

# Live preview only
d4v live-preview --live
```
