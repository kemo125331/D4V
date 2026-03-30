"""Vision pipeline configuration.

Centralized configuration for the combat text OCR pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VisionConfig:
    """Configuration for the combat text vision pipeline.

    Attributes:
        damage_roi: Relative ROI for damage text detection (left, top, width, height).
        ocr_psm_modes: Tesseract PSM modes to try, in priority order.
        ocr_whitelist: Character whitelist for OCR.
        min_confidence: Minimum confidence threshold for accepting hits.
        dedupe_frame_window: Frame window for temporal deduplication.
        dedupe_center_distance: Pixel distance threshold for spatial deduplication.
        max_line_candidates: Maximum line candidates to OCR per frame.
        image_upscale_factor: Upscale factor for OCR image preparation.
        ocr_border: Border pixels to add around OCR candidates.
        suffix_max_width: Maximum width for suffix token candidates (K, M, B).
        suffix_max_height: Maximum height for suffix token candidates.
        suffix_max_gap: Maximum gap to adjacent suffix token.
        suffix_max_vertical_drift: Max vertical drift for suffix alignment.
    """

    damage_roi: tuple[float, float, float, float] = (0.15, 0.05, 0.70, 0.75)
    ocr_psm_modes: tuple[int, ...] = (8, 7)  # Two modes for better suffix capture
    ocr_whitelist: str = "0123456789.,kKmMbB"
    min_confidence: float = 0.2  # Lower to catch more hits
    dedupe_frame_window: int = 3
    dedupe_center_distance: float = 70.0
    max_line_candidates: int = 20  # More candidates to catch all damage numbers
    image_upscale_factor: int = 8  # Higher upscale for better suffix recognition
    ocr_border: int = 6  # More border context
    suffix_max_width: int = 200
    suffix_max_height: int = 120
    suffix_max_gap: int = 120
    suffix_max_vertical_drift: float = 0.55
