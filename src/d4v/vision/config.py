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

    # capture sub-image already covers only the combat area (10%–90% width, 2%–84% height)
    # so we use the full captured region here (no further cropping needed)
    damage_roi: tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0)
    # PSM 7 = single text line — best for D4 floating numbers.
    # Using a single mode avoids doubling the Tesseract call count (each call ~320ms).
    ocr_psm_modes: tuple[int, ...] = (7,)
    ocr_whitelist: str = "0123456789.,kKmMbB"
    min_confidence: float = 0.2
    dedupe_frame_window: int = 2
    dedupe_center_distance: float = 50.0
    # D4 rarely shows more than 6 simultaneous floating numbers; cap at 8 for safety.
    max_line_candidates: int = 8
    image_upscale_factor: int = 8
    ocr_border: int = 6
    suffix_max_width: int = 200
    suffix_max_height: int = 120
    suffix_max_gap: int = 120
    suffix_max_vertical_drift: float = 0.55
