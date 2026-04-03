"""Experimental features - not ready for production.

This module contains features that are:
- Incomplete or partially implemented
- Not integrated into the main pipeline
- Under active development
- May be removed or significantly changed

Modules:
- ocr_voting: Multi-frame OCR voting for improved accuracy
- high_fps_capture: 60 FPS capture for short-lived text detection
- adaptive_roi: Motion-based ROI tracking and expansion
- kill_inference: Kill tracking via damage patterns and visual cues
- enhanced_color_mask: Extended color segmentation for multiple damage types

Usage:
    from d4v.experimental import OcrVoteAggregator
    from d4v.experimental import ShortLivedTextDetector

Note: These features may become stable in future releases or be removed
if they don't meet quality/performance standards.
"""

from d4v.experimental.ocr_voting import (
    OcrVote,
    OcrVoteResult,
    TrackedDamage,
    OcrVoteAggregator,
    aggregate_ocr_results,
)

from d4v.experimental.high_fps_capture import (
    CapturedFrame,
    FrameBuffer,
    HighFpsCapture,
    ShortLivedTextDetector,
    ShortLivedTextConfig,
    optimize_for_short_lived_text,
)

from d4v.experimental.adaptive_roi import (
    MotionRegion,
    AdaptiveRoiState,
    MotionDetector,
    AdaptiveRoiTracker,
    RoiPredictor,
)

from d4v.experimental.kill_inference import (
    KillSignal,
    KillEvent,
    EnemyState,
    KillStatistics,
    KillTracker,
    infer_kills_from_damage,
)

from d4v.experimental.enhanced_color_mask import (
    DamageColor,
    ColorRange,
    EnhancedColorMask,
    build_enhanced_combat_text_mask,
)

__all__ = [
    # OCR Voting
    "OcrVote",
    "OcrVoteResult",
    "TrackedDamage",
    "OcrVoteAggregator",
    "aggregate_ocr_results",
    # High-FPS Capture
    "CapturedFrame",
    "FrameBuffer",
    "HighFpsCapture",
    "ShortLivedTextDetector",
    "ShortLivedTextConfig",
    "optimize_for_short_lived_text",
    # Adaptive ROI
    "MotionRegion",
    "AdaptiveRoiState",
    "MotionDetector",
    "AdaptiveRoiTracker",
    "RoiPredictor",
    # Kill Inference
    "KillSignal",
    "KillEvent",
    "EnemyState",
    "KillStatistics",
    "KillTracker",
    "infer_kills_from_damage",
    # Enhanced Color Mask
    "DamageColor",
    "ColorRange",
    "EnhancedColorMask",
    "build_enhanced_combat_text_mask",
]

# Experimental status flag
EXPERIMENTAL = True
