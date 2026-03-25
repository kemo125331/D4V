# D4 Combat Overlay Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Windows-only Diablo IV overlay that estimates visible damage in real time and lays the foundation for an experimental kill counter.

**Architecture:** Use a Python-first desktop architecture with separate capture, vision, domain, overlay, and storage modules. The first milestone is replayable signal validation from recorded footage, then a live overlay once the damage pipeline is good enough.

**Tech Stack:** Python, `mss`, `opencv-python`, `numpy`, `PySide6`, `pytest`, `uv`

---

### Task 1: Bootstrap The Repository

**Files:**
- Create: `pyproject.toml`
- Create: `src/d4v/__init__.py`
- Create: `src/d4v/app.py`
- Create: `tests/test_smoke.py`

**Step 1: Write the failing test**

```python
from d4v import __version__


def test_version_is_defined():
    assert isinstance(__version__, str)
    assert __version__
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_smoke.py -v`
Expected: FAIL because the package does not exist yet

**Step 3: Write minimal implementation**

```python
__version__ = "0.1.0"
```

```python
def main() -> int:
    return 0
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_smoke.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add pyproject.toml src/d4v/__init__.py src/d4v/app.py tests/test_smoke.py
git commit -m "chore: bootstrap d4v package"
```

### Task 2: Add Window Detection And Screen Capture

**Files:**
- Create: `src/d4v/capture/__init__.py`
- Create: `src/d4v/capture/game_window.py`
- Create: `src/d4v/capture/screen_capture.py`
- Create: `src/d4v/domain/models.py`
- Test: `tests/capture/test_game_window.py`
- Test: `tests/capture/test_screen_capture.py`

**Step 1: Write the failing tests**

```python
from d4v.capture.game_window import GameWindowBounds


def test_bounds_width_and_height_are_positive():
    bounds = GameWindowBounds(left=10, top=20, width=300, height=200)
    assert bounds.width == 300
    assert bounds.height == 200
```

```python
from d4v.capture.screen_capture import normalize_roi


def test_normalize_roi_clamps_to_window():
    roi = normalize_roi((900, 900, 400, 300), window_size=(1024, 1024))
    assert roi == (900, 900, 124, 124)
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/capture/test_game_window.py tests/capture/test_screen_capture.py -v`
Expected: FAIL because capture modules do not exist yet

**Step 3: Write minimal implementation**

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class GameWindowBounds:
    left: int
    top: int
    width: int
    height: int
```

```python
def normalize_roi(roi, window_size):
    x, y, w, h = roi
    max_w, max_h = window_size
    return (x, y, max(0, min(w, max_w - x)), max(0, min(h, max_h - y)))
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/capture/test_game_window.py tests/capture/test_screen_capture.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/d4v/capture src/d4v/domain tests/capture
git commit -m "feat: add window and capture foundations"
```

### Task 3: Build Replay-First Damage Parsing

**Files:**
- Create: `src/d4v/vision/__init__.py`
- Create: `src/d4v/vision/preprocess.py`
- Create: `src/d4v/vision/damage_reader.py`
- Create: `src/d4v/vision/dedupe.py`
- Create: `tests/vision/test_damage_reader.py`
- Create: `tests/vision/test_dedupe.py`
- Create: `fixtures/replays/.gitkeep`

**Step 1: Write the failing tests**

```python
from d4v.vision.dedupe import dedupe_events


def test_dedupe_events_keeps_unique_hits():
    events = [
        {"frame": 1, "value": 1200},
        {"frame": 2, "value": 1200},
        {"frame": 5, "value": 9800},
    ]
    assert dedupe_events(events, frame_window=2) == [
        {"frame": 1, "value": 1200},
        {"frame": 5, "value": 9800},
    ]
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/vision/test_damage_reader.py tests/vision/test_dedupe.py -v`
Expected: FAIL because vision modules do not exist yet

**Step 3: Write minimal implementation**

```python
def dedupe_events(events, frame_window):
    result = []
    last_seen = {}
    for event in events:
        frame = event["frame"]
        value = event["value"]
        if value in last_seen and frame - last_seen[value] <= frame_window:
            continue
        last_seen[value] = frame
        result.append(event)
    return result
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/vision/test_damage_reader.py tests/vision/test_dedupe.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/d4v/vision tests/vision fixtures/replays/.gitkeep
git commit -m "feat: add replay-first damage parsing foundation"
```

### Task 4: Add Session Stats Aggregation

**Files:**
- Create: `src/d4v/domain/session_stats.py`
- Create: `tests/domain/test_session_stats.py`

**Step 1: Write the failing test**

```python
from d4v.domain.session_stats import SessionStats


def test_session_stats_updates_total_and_peak():
    stats = SessionStats()
    stats.add_hit(frame=1, timestamp_ms=1000, value=1200)
    stats.add_hit(frame=2, timestamp_ms=1200, value=9800)
    assert stats.visible_damage_total == 11000
    assert stats.peak_hit == 9800
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/domain/test_session_stats.py -v`
Expected: FAIL because the session stats module does not exist yet

**Step 3: Write minimal implementation**

```python
class SessionStats:
    def __init__(self):
        self.visible_damage_total = 0
        self.peak_hit = 0

    def add_hit(self, frame, timestamp_ms, value):
        self.visible_damage_total += value
        self.peak_hit = max(self.peak_hit, value)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/domain/test_session_stats.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/d4v/domain/session_stats.py tests/domain/test_session_stats.py
git commit -m "feat: add session stat aggregation"
```

### Task 5: Build A Minimal Overlay Shell

**Files:**
- Create: `src/d4v/overlay/__init__.py`
- Create: `src/d4v/overlay/window.py`
- Create: `src/d4v/overlay/view_model.py`
- Create: `tests/overlay/test_view_model.py`

**Step 1: Write the failing test**

```python
from d4v.overlay.view_model import OverlayViewModel


def test_overlay_view_model_formats_damage_total():
    vm = OverlayViewModel()
    vm.visible_damage_total = 12500
    assert vm.damage_label == "12,500"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/overlay/test_view_model.py -v`
Expected: FAIL because the overlay modules do not exist yet

**Step 3: Write minimal implementation**

```python
class OverlayViewModel:
    def __init__(self):
        self.visible_damage_total = 0

    @property
    def damage_label(self):
        return f"{self.visible_damage_total:,}"
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/overlay/test_view_model.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/d4v/overlay tests/overlay
git commit -m "feat: add minimal overlay shell"
```

### Task 6: Add Diagnostics And Experimental Kill Tracking

**Files:**
- Create: `src/d4v/vision/kill_detector.py`
- Create: `src/d4v/diagnostics/__init__.py`
- Create: `src/d4v/diagnostics/panel.py`
- Create: `tests/vision/test_kill_detector.py`

**Step 1: Write the failing test**

```python
from d4v.vision.kill_detector import KillDetector


def test_kill_detector_starts_with_zero_estimated_kills():
    detector = KillDetector()
    assert detector.estimated_kills == 0
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/vision/test_kill_detector.py -v`
Expected: FAIL because the kill detector does not exist yet

**Step 3: Write minimal implementation**

```python
class KillDetector:
    def __init__(self):
        self.estimated_kills = 0
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/vision/test_kill_detector.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/d4v/vision/kill_detector.py src/d4v/diagnostics tests/vision/test_kill_detector.py
git commit -m "feat: add diagnostics and experimental kill tracking"
```

