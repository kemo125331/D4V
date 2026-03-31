# D4V Detection Improvements - Implementation Plan

**Created:** 2026-03-30  
**Version:** 1.0  
**Status:** Planning Complete  

---

## Executive Summary

This plan outlines 15 improvements to the D4V combat text detection system, organized into 4 phases over ~8 weeks. The improvements target accuracy, performance, feature completeness, and platform support.

**Current State:**
- Vision-first OCR pipeline using OpenCV + WinOCR
- Heuristic confidence scoring (0.6 threshold)
- Fixed ROI, single-frame processing
- Windows-only, no formal benchmarks
- ~70% estimated accuracy (unvalidated)

**Target State:**
- ML-enhanced confidence scoring with ground truth validation
- Adaptive ROI with motion prediction
- Multi-frame voting, enhanced color segmentation
- Cross-platform support (Windows, Linux, macOS)
- >90% precision/recall with published benchmarks

---

## Phase 1: Foundation & Benchmarking (Week 1-2)

### Task 1: Ground Truth Benchmarking Infrastructure
**Priority:** 🔴 Critical | **Effort:** 3 days | **Dependencies:** None

**Objective:** Establish validated dataset and metrics framework

**Implementation:**
```
fixtures/
├── benchmarks/
│   ├── benchmark_v1.json           # Ground truth annotations
│   ├── benchmark_metrics.json      # Precision/recall results
│   └── README.md                   # Annotation guidelines
└── replays/
    ├── session_001/                # Annotated session
    │   ├── frames/                 # frame_0001.png, ...
    │   └── annotations.json        # Frame-level ground truth
    └── session_002/
```

**Files to Create:**
- `src/d4v/benchmark/runner.py` - Benchmark execution engine
- `src/d4v/benchmark/metrics.py` - Precision/recall/F1 calculation
- `src/d4v/benchmark/annotation.py` - Annotation format helpers
- `tests/benchmark/test_runner.py` - Benchmark tests

**Test Plan:**
```python
# tests/benchmark/test_metrics.py
def test_precision_calculation():
    # Given: 100 detected hits, 85 true positives, 15 false positives
    # Expect: precision = 85 / (85 + 15) = 0.85

def test_recall_calculation():
    # Given: 100 actual hits in ground truth, 90 detected
    # Expect: recall = 90 / 100 = 0.90

def test_f1_score():
    # Given: precision=0.85, recall=0.90
    # Expect: F1 = 2 * (0.85 * 0.90) / (0.85 + 0.90) = 0.874
```

**Acceptance Criteria:**
- [ ] Can load annotated replay fixtures
- [ ] Computes precision, recall, F1, accuracy
- [ ] Generates comparison reports (before/after changes)
- [ ] Documents annotation format and process

---

### Task 2: Enhanced Logging & Diagnostics
**Priority:** 🔴 Critical | **Effort:** 2 days | **Dependencies:** None

**Objective:** Comprehensive logging for troubleshooting and analysis

**Implementation:**
```python
# src/d4v/logging/detection_logger.py
@dataclass
class DetectionLogEntry:
    frame_index: int
    timestamp_ms: int
    candidates_examined: int
    hits_accepted: int
    hits_rejected: list[RejectionReason]
    processing_time_ms: float
    snapshot_path: Path | None  # Optional frame snapshot

class RejectionReason(StrEnum):
    LOW_CONFIDENCE = "low_confidence"
    IMPLAUSIBLE_TEXT = "implausible_text"
    DUPLICATE = "duplicate"
    INVALID_PARSE = "invalid_parse"
    SIZE_CONSTRAINT = "size_constraint"
```

**Files to Create:**
- `src/d4v/logging/detection_logger.py` - Structured logging
- `src/d4v/logging/snapshot_capture.py` - Frame snapshot on failure
- `src/d4v/logging/metrics_logger.py` - Session-level metrics

**Test Plan:**
```python
# tests/logging/test_detection_logger.py
def test_log_rejection_reasons():
    # Given: Hit rejected for low confidence
    # Expect: Log entry contains rejection reason and snapshot

def test_snapshot_capture_on_failure():
    # Given: Detection failure with snapshot enabled
    # Expect: PNG saved to temp directory with metadata JSON
```

**Acceptance Criteria:**
- [ ] Logs all detection decisions with reasons
- [ ] Captures frame snapshots on configurable failure conditions
- [ ] Session summary with detection rates, timing stats
- [ ] Opt-in telemetry export for analysis

---

### Task 3: Pipeline Profiling & Performance Baseline
**Priority:** 🟡 High | **Effort:** 2 days | **Dependencies:** Task 2

**Objective:** Measure and optimize pipeline latency

**Implementation:**
```python
# src/d4v/profiling/pipeline_profiler.py
@dataclass
class StageProfile:
    stage_name: str
    mean_time_ms: float
    p95_time_ms: float
    p99_time_ms: float
    std_dev_ms: float

class PipelineProfiler:
    def profile_stage(self, stage: str, func: Callable) -> Callable:
        # Wrap pipeline stages with timing
```

**Files to Create:**
- `src/d4v/profiling/pipeline_profiler.py` - Stage timing
- `src/d4v/profiling/memory_profiler.py` - Memory usage tracking
- `tests/profiling/test_profiler.py` - Profiler tests

**Test Plan:**
```python
# tests/profiling/test_pipeline_profiler.py
def test_stage_timing_accuracy():
    # Given: Mock stage with 10ms sleep
    # Expect: Measured time within 1ms of actual

def test_p95_calculation():
    # Given: 100 measurements with known distribution
    # Expect: P95 within 5% of expected value
```

**Acceptance Criteria:**
- [ ] Profiles each pipeline stage (mask, segment, group, OCR, parse)
- [ ] Reports mean, P95, P99 latencies
- [ ] Identifies bottlenecks automatically
- [ ] Baseline: <50ms per frame at 1080p

---

### Task 4: Expand Test Fixtures
**Priority:** 🟡 High | **Effort:** 3 days | **Dependencies:** Task 1

**Objective:** Comprehensive test coverage for edge cases

**Fixture Scenarios:**
```
fixtures/replays/
├── scenario_001_normal_combat/     # Standard combat, good lighting
├── scenario_002_low_fps/           # Frame drops, stuttering
├── scenario_003_screen_clutter/    # Multiple UI elements, party play
├── scenario_004_different_zones/   # Various zone lighting conditions
├── scenario_005_crit_heavy/        # High crit rate, large numbers
├── scenario_006_dot_damage/        # DoT ticks, overlapping numbers
├── scenario_007_resource_changes/  # Spirit/Mana displays
└── scenario_008_edge_cases/        # Min/max damage, suffixes
```

**Files to Create:**
- `fixtures/replays/*/annotations.json` for each scenario
- `tests/vision/test_edge_cases.py` - Edge case tests
- `tests/tools/test_replay_analysis.py` - Replay tool tests

**Test Plan:**
```python
# tests/vision/test_edge_cases.py
def test_low_fps_detection():
    # Given: Replay with 15 FPS capture
    # Expect: No missed hits >1000 damage

def test_screen_clutter_false_positives():
    # Given: Frame with party UI, buffs, multiple players
    # Expect: <5% false positive rate

def test_overlapping_damage_numbers():
    # Given: 3+ damage numbers overlapping
    # Expect: At least 2 of 3 correctly parsed
```

**Acceptance Criteria:**
- [ ] 8+ annotated replay scenarios
- [ ] Automated regression test suite
- [ ] Edge case coverage documented
- [ ] Replay analysis tools functional

---

## Phase 2: Detection Accuracy (Week 3-5)

### Task 5: ML-Based Confidence Scoring
**Priority:** 🔴 Critical | **Effort:** 5 days | **Dependencies:** Task 1, Task 4

**Objective:** Replace heuristic scoring with trained classifier

**Implementation:**
```python
# src/d4v/vision/confidence_model.py
@dataclass
class ConfidenceFeatures:
    line_score: float
    fill_ratio: float
    aspect_ratio: float
    member_count: int
    parsed_value: int | None
    has_suffix: bool
    digit_count: int
    width: int
    height: int
    ocr_raw_text: str

class ConfidenceClassifier:
    def __init__(self, model_path: Path | None = None):
        self.model = self._load_or_create_model(model_path)
    
    def predict_confidence(self, features: ConfidenceFeatures) -> float:
        # Returns calibrated probability (0.0-1.0)
```

**Training Data Requirements:**
- 500+ labeled OCR candidates (positive/negative)
- Features: line metrics, parse results, text patterns
- Model: Logistic Regression or small MLP (scikit-learn)

**Files to Create:**
- `src/d4v/vision/confidence_model.py` - ML classifier
- `src/d4v/vision/training_data.py` - Training data loader
- `scripts/train_confidence_model.py` - Training script
- `tests/vision/test_confidence_model.py` - Model tests

**Test Plan:**
```python
# tests/vision/test_confidence_model.py
def test_model_calibration():
    # Given: 100 predictions with confidence 0.7-0.8
    # Expect: ~75% accuracy in that bin (calibration curve)

def test_model_vs_heuristic():
    # Given: Benchmark dataset
    # Expect: ML model F1 > heuristic F1 by 10%

def test_feature_importance():
    # Given: Trained model
    # Expect: Top 3 features match domain knowledge
```

**Acceptance Criteria:**
- [ ] Trained model with >85% accuracy on validation set
- [ ] Calibration curve shows good probability estimates
- [ ] Outperforms heuristic baseline by 10%+ F1
- [ ] Model serialization and loading works
- [ ] Fallback to heuristic if model unavailable

---

### Task 6: Multi-Frame OCR Voting
**Priority:** 🟡 High | **Effort:** 3 days | **Dependencies:** Task 5

**Objective:** Improve OCR consistency across frames

**Implementation:**
```python
# src/d4v/vision/ocr_voting.py
@dataclass
class OcrVote:
    frame_index: int
    parsed_value: int
    confidence: float
    center_x: float
    center_y: float

def aggregate_ocr_votes(
    votes: list[OcrVote],
    spatial_threshold: float = 70.0,
    frame_window: int = 3,
) -> OcrVoteResult:
    """
    Group votes by spatial proximity and frame window.
    Return consensus value with weighted voting.
    """
```

**Files to Create:**
- `src/d4v/vision/ocr_voting.py` - Voting aggregation
- `tests/vision/test_ocr_voting.py` - Voting tests

**Test Plan:**
```python
# tests/vision/test_ocr_voting.py
def test_consensus_with_outlier():
    # Given: 3 frames with values [1000, 1000, 950]
    # Expect: Consensus = 1000 (majority vote)

def test_spatial_grouping():
    # Given: 2 damage numbers at different positions
    # Expect: Separate vote groups, no cross-contamination

def test_weighted_by_confidence():
    # Given: Votes with confidences [0.9, 0.6, 0.9]
    # Expect: High-confidence votes dominate
```

**Acceptance Criteria:**
- [ ] Groups OCR results by spatial proximity
- [ ] Weighted voting by confidence score
- [ ] Handles outliers gracefully
- [ ] Reduces single-frame OCR errors by 30%+

---

### Task 7: Enhanced Color Segmentation
**Priority:** 🟡 High | **Effort:** 3 days | **Dependencies:** None

**Objective:** Support additional damage types and colors

**Implementation:**
```python
# src/d4v/vision/color_mask.py (enhanced)
COMBAT_TEXT_COLORS = {
    "yellow_orange": {"hue": (10, 30), "saturation": (120, 255), "value": (140, 255)},
    "white": {"hue": (0, 180), "saturation": (0, 40), "value": (190, 255)},
    "blue": {"hue": (90, 130), "saturation": (100, 255), "value": (140, 255)},
    "poison_green": {"hue": (50, 70), "saturation": (100, 255), "value": (140, 255)},
    "fire_red": {"hue": (0, 10), "saturation": (150, 255), "value": (140, 255)},
    "lighting_purple": {"hue": (130, 160), "saturation": (80, 255), "value": (140, 255)},
}

def build_combat_text_mask(
    image: Image.Image,
    enabled_colors: set[str] | None = None,
) -> Image.Image:
    # Configurable color mask with per-color tuning
```

**Files to Create:**
- `src/d4v/vision/color_mask.py` (enhanced)
- `src/d4v/vision/color_calibration.py` - Color calibration tool
- `tests/vision/test_color_mask.py` - Enhanced color tests

**Test Plan:**
```python
# tests/vision/test_color_mask.py
def test_poison_green_detection():
    # Given: Frame with poison DoT damage (green text)
    # Expect: Green text detected in mask

def test_fire_red_detection():
    # Given: Frame with fire damage (red text)
    # Expect: Red text detected in mask

def test_color_mask_tuning():
    # Given: User-provided color sample
    # Expect: Calibrated mask captures 90%+ of target color
```

**Acceptance Criteria:**
- [ ] Supports 6+ damage type colors
- [ ] Configurable per-color thresholds
- [ ] Color calibration tool for user tuning
- [ ] Backward compatible with existing config

---

### Task 8: Enhanced Deduplication
**Priority:** 🟡 High | **Effort:** 3 days | **Dependencies:** Task 6

**Objective:** Track text velocity and handle overlaps

**Implementation:**
```python
# src/d4v/vision/tracking.py
@dataclass
class TrackedText:
    id: int
    first_frame: int
    last_frame: int
    positions: list[tuple[float, float]]  # (center_x, center_y)
    values: list[int]
    velocity_y: float  # Pixels per frame (damage floats upward)

class TextTracker:
    def update(self, detections: list[Detection], frame_index: int) -> list[TrackedText]:
        # Match detections to existing tracks using Kalman filter or simple motion model
        # Handle occlusions and overlaps
```

**Files to Create:**
- `src/d4v/vision/tracking.py` - Multi-object tracking
- `tests/vision/test_tracking.py` - Tracking tests

**Test Plan:**
```python
# tests/vision/test_tracking.py
def test_velocity_prediction():
    # Given: Text moving upward at 10px/frame
    # Expect: Predicted position within 5px of actual

def test_overlap_handling():
    # Given: 2 damage numbers crossing paths
    # Expect: Both tracked separately, no ID swaps

def test_track_termination():
    # Given: Text fades out after 15 frames
    # Expect: Track marked complete, final value recorded
```

**Acceptance Criteria:**
- [ ] Tracks text across 5+ frames
- [ ] Predicts position using velocity model
- [ ] Handles overlaps without ID swaps
- [ ] Reduces duplicate counting by 50%+

---

### Task 9: Adaptive ROI Tracking
**Priority:** 🟡 High | **Effort:** 4 days | **Dependencies:** Task 8

**Objective:** Dynamic ROI based on motion and activity

**Implementation:**
```python
# src/d4v/vision/adaptive_roi.py
@dataclass
class AdaptiveRoiConfig:
    base_roi: tuple[float, float, float, float]
    expansion_margin: int = 50
    motion_threshold: int = 100  # Pixels changed to trigger expansion
    cooldown_frames: int = 30

class AdaptiveRoiTracker:
    def __init__(self, config: AdaptiveRoiConfig):
        self.config = config
        self.active_regions: list[Rectangle] = []
        self.motion_history: deque[FrameDiff] = deque(maxlen=10)
    
    def compute_roi(self, current_frame: Image, previous_frame: Image) -> tuple[int, int, int, int]:
        # Detect motion regions
        # Expand base ROI if activity detected
        # Return optimized crop region
```

**Files to Create:**
- `src/d4v/vision/adaptive_roi.py` - Motion-based ROI
- `tests/vision/test_adaptive_roi.py` - Adaptive ROI tests

**Test Plan:**
```python
# tests/vision/test_adaptive_roi.py
def test_motion_triggered_expansion():
    # Given: Damage appears outside base ROI
    # Expect: ROI expands to include new damage within 2 frames

def test_roi_contraction():
    # Given: No activity in expanded region for 30 frames
    # Expect: ROI contracts to base size

def test_multiple_activity_centers():
    # Given: Damage in 2 separate screen regions
    # Expect: ROI covers both or prioritizes higher activity
```

**Acceptance Criteria:**
- [ ] Detects motion outside base ROI
- [ ] Expands ROI within 2 frames of new activity
- [ ] Contracts after inactivity cooldown
- [ ] Captures 95%+ of damage vs 85% with fixed ROI

---

## Phase 3: Feature Enhancements (Week 6-7)

### Task 10: Damage Type Classification
**Priority:** 🟢 Medium | **Effort:** 4 days | **Dependencies:** Task 7

**Objective:** Classify damage by type (direct, DoT, crit, shield)

**Implementation:**
```python
# src/d4v/vision/damage_classifier.py
class DamageType(StrEnum):
    DIRECT = "direct"
    CRIT = "crit"
    DOT_TICK = "dot_tick"
    SHIELD_GAIN = "shield_gain"
    HEALING = "healing"
    RESOURCE = "resource"

@dataclass
class ClassifiedDamage:
    value: int
    damage_type: DamageType
    confidence: float
    color_hint: str | None
    size_hint: str | None  # Crits are often larger

class DamageTypeClassifier:
    def classify(self, detection: Detection) -> ClassifiedDamage:
        # Features: color, size, value pattern, frequency
        # Crit: larger font, often yellow/orange
        # DoT: small values, rapid ticks, green/red
```

**Files to Create:**
- `src/d4v/vision/damage_classifier.py` - Type classification
- `tests/vision/test_damage_classifier.py` - Classifier tests

**Test Plan:**
```python
# tests/vision/test_damage_classifier.py
def test_crit_classification():
    # Given: Large damage number (2x normal size)
    # Expect: Classified as CRIT with >0.8 confidence

def test_dot_tick_classification():
    # Given: Rapid small damage ticks (50-100)
    # Expect: Classified as DOT_TICK

def test_shield_gain_classification():
    # Given: Blue text with shield icon nearby
    # Expect: Classified as SHIELD_GAIN
```

**Acceptance Criteria:**
- [ ] Classifies 5+ damage types
- [ ] Uses color, size, pattern features
- [ ] >80% accuracy on validation set
- [ ] Enables per-type DPS breakdown

---

### Task 11: Kill Tracking Pipeline
**Priority:** 🟢 Medium | **Effort:** 5 days | **Dependencies:** Task 10

**Objective:** Infer enemy kills from damage and death signals

**Implementation:**
```python
# src/d4v/domain/kill_inference.py
@dataclass
class KillEvent:
    timestamp_ms: int
    frame_index: int
    total_damage_dealt: int
    final_hit_value: int
    kill_signal: str  # "xp_orb", "gold_drop", "death_animation"
    confidence: float

class KillTracker:
    def __init__(self):
        self.active_enemies: dict[int, EnemyState] = {}
        self.damage_window_ms: int = 3000  # 3 second damage window
    
    def process_frame(self, detections: list[Detection], visual_cues: list[VisualCue]):
        # Track damage per enemy (spatial clustering)
        # Detect death signals: XP orbs, gold, animations
        # Infer kill when damage + death signal coincide
```

**Files to Create:**
- `src/d4v/domain/kill_inference.py` - Kill detection
- `src/d4v/vision/visual_cue_detector.py` - XP orb, gold detection
- `tests/domain/test_kill_inference.py` - Kill tracking tests

**Test Plan:**
```python
# tests/domain/test_kill_inference.py
def test_kill_with_xp_orb():
    # Given: Damage sequence followed by XP orb appearance
    # Expect: KillEvent with xp_orb signal

def test_kill_with_gold_drop():
    # Given: Damage followed by gold pickup text
    # Expect: KillEvent with gold_drop signal

def test_false_positive_suppression():
    # Given: Damage with no death signal for 5 seconds
    # Expect: No kill event (enemy may have leashed)
```

**Acceptance Criteria:**
- [ ] Detects XP orbs, gold drops, item drops
- [ ] Correlates damage with death signals
- [ ] Tracks damage per enemy (spatial clustering)
- [ ] Reports kill count, biggest kill, kills per minute

---

### Task 12: Short-Lived Text Recall
**Priority:** 🟡 High | **Effort:** 4 days | **Dependencies:** Task 3, Task 8

**Objective:** Capture fast-fading damage numbers

**Implementation:**
```python
# src/d4v/capture/high_fps_capture.py
class HighFpsCapture:
    def __init__(self, target_fps: int = 60):
        self.target_fps = target_fps
        self.frame_interval_ms = 1000 // target_fps
    
    def capture_loop(self):
        # Run capture at target FPS
        # Use async processing to avoid blocking

# src/d4v/vision/motion_prediction.py
class MotionPredictor:
    def predict_text_appearance(
        self,
        recent_detections: list[Detection],
    ) -> list[PredictedRegion]:
        # Analyze damage spawn patterns
        # Predict where new damage will appear
        # Prioritize OCR in high-probability regions
```

**Files to Create:**
- `src/d4v/capture/high_fps_capture.py` - High FPS capture
- `src/d4v/vision/motion_prediction.py` - Spawn prediction
- `tests/capture/test_high_fps.py` - High FPS tests

**Test Plan:**
```python
# tests/capture/test_high_fps_capture.py
def test_60fps_capture():
    # Given: Fast combat with short-lived numbers
    # Expect: 60 FPS capture misses 50%+ fewer hits than 30 FPS

def test_motion_prediction_accuracy():
    # Given: 100 damage spawns
    # Expect: 80% appear in predicted regions
```

**Acceptance Criteria:**
- [ ] Supports 60 FPS capture (configurable)
- [ ] Reduces missed short-lived text by 50%+
- [ ] Motion prediction improves capture efficiency
- [ ] Async processing avoids frame drops

---

## Phase 4: Platform & Polish (Week 8)

### Task 13: Resolution/UI Scale Auto-Detection
**Priority:** 🟡 High | **Effort:** 4 days | **Dependencies:** Task 1

**Objective:** Auto-detect and calibrate for resolution/scale

**Implementation:**
```python
# src/d4v/vision/resolution_detector.py
@dataclass
class ResolutionProfile:
    width: int
    height: int
    ui_scale: float
    calibrated_rois: dict[str, tuple[float, float, float, float]]
    calibrated_thresholds: dict[str, float]

class ResolutionDetector:
    def detect_game_resolution(self) -> GameWindowBounds | None:
        # Query game window for client rect
    
    def estimate_ui_scale(self, sample_frames: list[Image]) -> float:
        # Analyze damage text size relative to screen
        # Infer UI scale setting (100%, 125%, 150%, etc.)
    
    def load_or_create_profile(self, resolution: ResolutionKey) -> ResolutionProfile:
        # Load existing calibration or create new
```

**Files to Create:**
- `src/d4v/vision/resolution_detector.py` - Auto-detection
- `src/d4v/vision/calibration_wizard.py` - User calibration UI
- `tests/vision/test_resolution_detector.py` - Detector tests

**Test Plan:**
```python
# tests/vision/test_resolution_detector.py
def test_resolution_detection():
    # Given: Game window at 1920x1080
    # Expect: Correct resolution detected

def test_ui_scale_estimation():
    # Given: Frames with known text sizes at 150% UI scale
    # Expect: Estimated scale within 10% of actual

def test_profile_persistence():
    # Given: Calibration saved for resolution
    # Expect: Profile loads correctly on next session
```

**Acceptance Criteria:**
- [ ] Auto-detects game resolution
- [ ] Estimates UI scale within 10%
- [ ] Stores calibration profiles per resolution
- [ ] Calibration wizard for manual tuning
- [ ] Supports 5+ common resolutions

---

### Task 14: Visual Debug Overlay
**Priority:** 🟢 Medium | **Effort:** 3 days | **Dependencies:** Task 2

**Objective:** Real-time visualization for troubleshooting

**Implementation:**
```python
# src/d4v/overlay/debug_overlay.py
class DebugOverlay:
    def __init__(self, config: DebugConfig):
        self.config = config
        self.show_rois: bool = True
        self.show_candidates: bool = True
        self.show_confidence: bool = True
    
    def render(self, frame: Image, detections: list[Detection]) -> Image:
        # Draw ROIs (green = active, red = inactive)
        # Draw bounding boxes (color = confidence)
        # Draw text labels (value, confidence, parse status)
        # Draw motion vectors (if tracking enabled)
```

**Files to Create:**
- `src/d4v/overlay/debug_overlay.py` - Debug visualization
- `tests/overlay/test_debug_overlay.py` - Overlay tests

**Test Plan:**
```python
# tests/overlay/test_debug_overlay.py
def test_roi_rendering():
    # Given: Frame with configured ROIs
    # Expect: ROIs drawn with correct coordinates

def test_confidence_color_coding():
    # Given: Detections with varying confidence
    # Expect: Green (high), yellow (medium), red (low)

def test_performance_overhead():
    # Given: Debug overlay enabled
    # Expect: <5ms rendering overhead per frame
```

**Acceptance Criteria:**
- [ ] Shows ROIs, bounding boxes, confidence scores
- [ ] Color-codes by confidence and parse status
- [ ] Toggle-able debug layers
- [ ] <5ms rendering overhead
- [ ] Works in live preview and replay analysis

---

### Task 15: Cross-Platform Window Detection
**Priority:** 🟢 Medium | **Effort:** 5 days | **Dependencies:** None

**Objective:** Abstract window detection for Windows, Linux, macOS

**Implementation:**
```python
# src/d4v/capture/window_detector.py
class WindowDetector(Protocol):
    def find_game_window(self, title_pattern: str) -> GameWindowBounds | None:
        ...

class WindowsWindowDetector:
    # Win32 API: FindWindowW, GetClientRect

class LinuxWindowDetector:
    # X11: XQueryTree, XGetWindowProperty
    # Wayland: DBus interface to compositor

class MacOsWindowDetector:
    # Quartz: CGWindowListCopyWindowInfo
    # Accessibility API: AXUIElement

def get_window_detector() -> WindowDetector:
    if sys.platform == "win32":
        return WindowsWindowDetector()
    elif sys.platform == "linux":
        return LinuxWindowDetector()
    elif sys.platform == "darwin":
        return MacOsWindowDetector()
```

**Files to Create:**
- `src/d4v/capture/window_detector.py` - Cross-platform abstraction
- `src/d4v/capture/linux_window_detector.py` - X11/Wayland support
- `src/d4v/capture/macos_window_detector.py` - macOS support
- `tests/capture/test_window_detector.py` - Cross-platform tests

**Test Plan:**
```python
# tests/capture/test_window_detector.py
def test_windows_detector():
    # Given: Diablo IV window open on Windows
    # Expect: Window bounds detected correctly

def test_linux_detector():
    # Given: Game window on X11 or Wayland
    # Expect: Window bounds detected (skip if not on Linux)

def test_macos_detector():
    # Given: Game window on macOS
    # Expect: Window bounds detected (skip if not on macOS)
```

**Acceptance Criteria:**
- [ ] Windows: Win32 API (existing, refactored)
- [ ] Linux: X11 support, Wayland best-effort
- [ ] macOS: Quartz/Accessibility API
- [ ] Platform detection automatic
- [ ] Graceful degradation on unsupported platforms

---

## Testing Strategy

### Test Pyramid

```
                    ┌─────────────┐
                    │   E2E       │  ~10% - Full pipeline with replays
                   ─┴─────────────┴─
                  │ Integration Tests │  ~30% - Component interactions
                 ─┴───────────────────┴─
                │    Unit Tests        │  ~60% - Individual functions
```

### Test Categories

| Category | Location | Count | Purpose |
|----------|----------|-------|---------|
| Unit Tests | `tests/vision/`, `tests/domain/` | 50+ | Test individual functions |
| Integration Tests | `tests/tools/` | 15+ | Test component interactions |
| E2E Tests | `tests/benchmark/` | 8+ | Full pipeline with annotated replays |
| Performance Tests | `tests/profiling/` | 5+ | Latency and memory benchmarks |

### Test Execution

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/d4v --cov-report=html

# Run benchmark suite
pytest tests/benchmark/ --benchmark-only

# Run specific category
pytest tests/vision/ -v
pytest tests/domain/ -v
```

### Benchmark Suite

```bash
# Baseline measurement
python scripts/benchmark_pipeline.py --replay fixtures/replays/session_001/

# Compare before/after changes
python scripts/benchmark_pipeline.py --compare before.json after.json
```

---

## Success Metrics

### Accuracy Metrics (Measured via Benchmark)

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Precision | ~70% (est) | >90% | TP / (TP + FP) |
| Recall | ~70% (est) | >85% | TP / (TP + FN) |
| F1 Score | ~70% (est) | >87% | Harmonic mean |
| False Positive Rate | ~10% (est) | <5% | FP / (FP + TN) |

### Performance Metrics

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Pipeline Latency | ~100ms (est) | <50ms | P95 per-frame |
| FPS Capture | 30 FPS | 60 FPS | Sustained capture rate |
| Memory Usage | ~200MB (est) | <300MB | Peak RSS |
| CPU Usage | ~30% (est) | <20% | Average per-core |

### Feature Metrics

| Feature | Current | Target |
|---------|---------|--------|
| Damage Types | 3 colors | 6+ colors |
| Platform Support | Windows | Windows + Linux + macOS |
| Resolution Profiles | 1 preset | 5+ auto-detected |
| Kill Tracking | Not implemented | Implemented with 80% accuracy |

---

## Risk Mitigation

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| ML model underperforms | High | Medium | Keep heuristic fallback, A/B testing |
| Cross-platform bugs | Medium | High | CI on Windows/Linux/macOS, graceful degradation |
| Performance regression | High | Medium | Profiling in CI, performance budgets |
| Benchmark dataset bias | Medium | Medium | Diverse replay scenarios, community validation |
| User calibration complexity | Low | High | Simple wizard, sensible defaults |

---

## Rollout Plan

### Week 1-2: Foundation
- [ ] Task 1: Ground truth benchmarking
- [ ] Task 2: Enhanced logging
- [ ] Task 3: Pipeline profiling
- [ ] Task 4: Test fixtures

**Deliverable:** Benchmark suite with baseline metrics

### Week 3-5: Accuracy Improvements
- [ ] Task 5: ML confidence scoring
- [ ] Task 6: Multi-frame OCR voting
- [ ] Task 7: Enhanced color segmentation
- [ ] Task 8: Enhanced deduplication
- [ ] Task 9: Adaptive ROI

**Deliverable:** 15%+ F1 improvement, validated by benchmarks

### Week 6-7: Features
- [ ] Task 10: Damage type classification
- [ ] Task 11: Kill tracking
- [ ] Task 12: Short-lived text recall

**Deliverable:** Kill tracking, damage breakdown, improved recall

### Week 8: Platform & Polish
- [ ] Task 13: Resolution auto-detection
- [ ] Task 14: Visual debug overlay
- [ ] Task 15: Cross-platform support

**Deliverable:** Multi-platform release with debug tools

---

## Maintenance & Monitoring

### Post-Deployment Monitoring

```python
# Opt-in telemetry (user consent required)
{
    "session_id": "uuid4",
    "resolution": "1920x1080",
    "ui_scale": 1.0,
    "total_frames": 15000,
    "total_hits": 3500,
    "precision_estimate": 0.88,
    "recall_estimate": 0.85,
    "avg_latency_ms": 42,
    "platform": "win32",
    "version": "0.2.0"
}
```

### Continuous Improvement

1. **Monthly benchmark updates** - Add new replay scenarios
2. **Quarterly model retraining** - Incorporate user telemetry (opt-in)
3. **Community feedback loop** - GitHub issues, Discord for bug reports
4. **Performance regression testing** - CI on every PR

---

## Appendix: File Structure After Implementation

```
src/d4v/
├── benchmark/              # NEW: Benchmarking infrastructure
│   ├── runner.py
│   ├── metrics.py
│   └── annotation.py
├── capture/
│   ├── screen_capture.py
│   ├── game_window.py
│   ├── window_detector.py  # ENHANCED: Cross-platform
│   ├── high_fps_capture.py # NEW
│   └── recorder.py
├── vision/
│   ├── pipeline.py         # ENHANCED: ML confidence, voting
│   ├── config.py
│   ├── color_mask.py       # ENHANCED: Multi-color
│   ├── segments.py
│   ├── grouping.py
│   ├── ocr.py
│   ├── ocr_voting.py       # NEW
│   ├── classifier.py
│   ├── confidence_model.py # NEW
│   ├── dedupe.py
│   ├── tracking.py         # NEW
│   ├── adaptive_roi.py     # NEW
│   ├── resolution_detector.py # NEW
│   ├── damage_classifier.py   # NEW
│   ├── motion_prediction.py   # NEW
│   └── roi.py
├── domain/
│   ├── models.py
│   ├── session_aggregation.py
│   ├── session_stats.py
│   ├── kill_inference.py      # NEW
│   └── damage_types.py        # NEW
├── overlay/
│   ├── window.py
│   ├── view_model.py
│   └── debug_overlay.py       # NEW
├── logging/                   # NEW
│   ├── detection_logger.py
│   ├── snapshot_capture.py
│   └── metrics_logger.py
├── profiling/                 # NEW
│   ├── pipeline_profiler.py
│   └── memory_profiler.py
└── tools/
    ├── live_preview.py
    ├── analyze_replay_ocr.py
    ├── analyze_replay_roi.py
    ├── benchmark_runner.py    # NEW
    └── calibration_wizard.py  # NEW

tests/
├── benchmark/
├── vision/
├── domain/
├── capture/
├── overlay/
├── logging/
├── profiling/
└── tools/

fixtures/
├── benchmarks/
│   ├── benchmark_v1.json
│   └── benchmark_metrics.json
└── replays/
    ├── scenario_001_*/
    ├── scenario_002_*/
    └── ...
```

---

## Next Steps

1. **Review and approve this plan** - Confirm priorities and scope
2. **Set up benchmark infrastructure** (Task 1) - Foundation for validation
3. **Record initial replay fixtures** - 3-5 sessions with manual annotations
4. **Establish baseline metrics** - Run current pipeline on benchmarks
5. **Begin Phase 1 implementation** - Start with highest-priority tasks

---

**Questions or adjustments?** Let me know if you'd like to:
- Reprioritize tasks
- Adjust scope for specific tasks
- Add/remove features
- Change timeline estimates
