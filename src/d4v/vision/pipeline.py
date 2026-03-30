"""Protocol interfaces and CombatTextPipeline service.

Defines abstract interfaces for testability and the main vision pipeline service.
"""

from __future__ import annotations

import concurrent.futures
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

import PIL.ImageOps
from PIL import Image

from d4v.vision.classifier import is_plausible_damage_text, normalize_damage_text, parse_damage_value
from d4v.vision.color_mask import build_combat_text_mask
from d4v.vision.config import VisionConfig
from d4v.vision.grouping import GroupedCandidate, group_bounding_boxes
from d4v.vision.ocr import ocr_pil_image
from d4v.vision.segments import segment_damage_tokens
from d4v.vision.confidence_model import ConfidenceClassifier, ConfidenceFeatures

# Persistent thread pool — created once at import time, reused every frame.
# Avoids the ~15ms ThreadPoolExecutor setup cost per process_image call.
_OCR_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=4)

# Maximum width (px) for image fed into mask+segment. Input is downscaled to
# this before color masking — saves 47ms vs processing at 2048px.
_MAX_PROC_WIDTH = 1280


@dataclass(frozen=True)
class DetectedHit:
    """A detected damage hit from the vision pipeline.

    Attributes:
        frame_index: Frame number where hit was detected.
        timestamp_ms: Timestamp in milliseconds (if available).
        parsed_value: Parsed damage value.
        confidence: Confidence score (0.0 to 1.0).
        sample_text: Raw OCR text that produced this hit.
        center_x: X coordinate of hit center.
        center_y: Y coordinate of hit center.
    """

    frame_index: int
    timestamp_ms: int | None
    parsed_value: int
    confidence: float
    sample_text: str = ""
    center_x: float = 0.0
    center_y: float = 0.0


@runtime_checkable
class FrameSource(Protocol):
    """Protocol for frame capture sources."""

    def capture_frame(self) -> Image.Image | None:
        """Capture a single frame from the source.

        Returns:
            Captured PIL Image, or None if capture failed.
        """
        ...


@runtime_checkable
class HitSink(Protocol):
    """Protocol for hit consumption."""

    def add_hit(self, hit: DetectedHit) -> None:
        """Process a detected hit.

        Args:
            hit: The detected damage hit.
        """
        ...


@runtime_checkable
class FramePathSource(Protocol):
    """Protocol for frame path iteration (replay mode)."""

    def iter_frame_paths(self) -> list[Path]:
        """Return sorted list of frame paths.

        Returns:
            List of paths to frame PNG files.
        """
        ...


class CombatTextPipeline:
    """Combat text detection pipeline service.

    Encapsulates the vision pipeline for detecting damage numbers
    from captured frames. Supports both live capture and replay analysis.

    Attributes:
        config: Vision configuration parameters.
        confidence_classifier: ML-based confidence classifier.
    """

    def __init__(
        self,
        config: VisionConfig | None = None,
        model_path: Path | str | None = None,
    ) -> None:
        """Initialize the combat text pipeline.

        Args:
            config: Vision configuration. Uses defaults if not provided.
            model_path: Path to ML confidence model. Uses default if None.
        """
        self.config = config or VisionConfig()
        
        # Initialize ML confidence classifier
        if model_path is None:
            # Use default model location
            model_path = Path(__file__).parent.parent / "models" / "confidence_model.joblib"
        
        self.confidence_classifier = ConfidenceClassifier(
            model_path=Path(model_path),
            threshold=0.3,  # Lower threshold to catch more hits (was 0.5)
        )

    def process_image(
        self,
        image: Image.Image,
        frame_index: int,
        timestamp_ms: int,
    ) -> list[DetectedHit]:
        """Process a single image frame and detect damage hits."""
        from d4v.vision.roi import scale_relative_roi

        roi = scale_relative_roi(image.size, self.config.damage_roi)
        crop = image.crop((roi.left, roi.top, roi.right, roi.bottom)).convert("RGB")

        # --- Pre-downscale ------------------------------------------------
        # Benchmarked at 47ms saved on mask+segment vs full 2048px input.
        # OCR upscaling compensates — Tesseract never sees the downscaled size.
        # Also exclude bottom 12% (HUD/minimap) before any processing.
        crop = crop.crop((0, 0, crop.width, int(crop.height * 0.88)))
        if crop.width > _MAX_PROC_WIDTH:
            scale = _MAX_PROC_WIDTH / crop.width
            crop = crop.resize(
                (_MAX_PROC_WIDTH, int(crop.height * scale)),
                Image.BILINEAR,
            )
        # ------------------------------------------------------------------

        mask = build_combat_text_mask(crop)
        components = segment_damage_tokens(mask)
        grouped_candidates = group_bounding_boxes(components)

        ranked_lines = sorted(
            (
                grouped
                for grouped in grouped_candidates
                if self._is_ocr_ready_line(grouped)
            ),
            key=lambda grouped: self._score_line_candidate(grouped),
            reverse=True,
        )[: self.config.max_line_candidates]

        if not ranked_lines:
            return []

        # --- Parallel OCR (persistent pool) --------------------------------
        # WinOCR primary (1-15ms) + Tesseract fallback (120-300ms).
        # Tesseract releases the GIL; running N candidates concurrently keeps
        # fallback time near 1 call. Persistent pool saves startup overhead.
        def _ocr_group(grouped: GroupedCandidate) -> tuple[GroupedCandidate, str]:
            pad = self.config.ocr_border
            left = max(0, grouped.left - pad)
            top_ = max(0, grouped.top - pad)
            right = min(crop.width, grouped.right + pad + 1)
            bottom = min(crop.height, grouped.bottom + pad + 1)

            # Mask crop for Tesseract fallback
            line_mask = mask.crop((left, top_, right, bottom)).convert("L")

            # RGB crop for WinOCR (colour text on game background)
            rgb_crop = crop.crop((left, top_, right, bottom))

            text = ocr_pil_image(
                line_mask,
                psm_modes=self.config.ocr_psm_modes,
                whitelist=self.config.ocr_whitelist,
                rgb_source=rgb_crop,
            )
            return grouped, text

        # Include all grouped_candidates so suffix scan can read their text too
        all_ocr_targets = list({
            id(g): g for g in ranked_lines + [
                g for g in grouped_candidates if g not in ranked_lines
            ]
        }.values())

        ocr_futures = {_OCR_POOL.submit(_ocr_group, g): g for g in all_ocr_targets}
        group_text_cache: dict[tuple[int, int, int, int], str] = {}
        for future in concurrent.futures.as_completed(ocr_futures):
            try:
                g, text = future.result()
                group_text_cache[(g.left, g.top, g.right, g.bottom)] = text
            except Exception:
                pass
        # --------------------------------------------------------------------


        def read_group_text(grouped: GroupedCandidate) -> str:
            return group_text_cache.get(
                (grouped.left, grouped.top, grouped.right, grouped.bottom), ""
            )

        hits: list[DetectedHit] = []

        for grouped in ranked_lines:
            raw_text = read_group_text(grouped)
            normalized_text = normalize_damage_text(raw_text) if raw_text else ""

            # --- Suffix-first: always try to attach K/M/B before evaluating the
            # plain numeric value.  This fixes "1,000" + separate "K" token → 1_000_000.
            if self._is_plain_numeric_text(normalized_text):
                suffix_hint = self._find_adjacent_suffix_hint(
                    grouped, grouped_candidates, read_group_text
                )
                if suffix_hint is not None:
                    # Combine and re-normalise with the discovered suffix
                    raw_text = f"{normalized_text}{suffix_hint}"
                    normalized_text = normalize_damage_text(raw_text)

            parsed_value = parse_damage_value(normalized_text) if normalized_text else None
            confidence = self._score_ocr_result(
                raw_text=normalized_text,
                parsed_value=parsed_value,
                line_score=self._score_line_candidate(grouped),
                member_count=grouped.member_count,
                width=grouped.width,
                height=grouped.height,
                pixel_count=grouped.pixel_count,
            )

            if (
                parsed_value is None
                or confidence < self.config.min_confidence
                or not is_plausible_damage_text(normalized_text)
            ):
                continue

            hits.append(
                DetectedHit(
                    frame_index=frame_index,
                    timestamp_ms=timestamp_ms,
                    parsed_value=parsed_value,
                    confidence=confidence,
                    sample_text=raw_text,
                    center_x=(grouped.left + grouped.right) / 2,
                    center_y=(grouped.top + grouped.bottom) / 2,
                )
            )

        return hits

    def _is_plain_numeric_text(self, text: str) -> bool:
        """Check if text is a plain numeric damage value."""
        if not text:
            return False
        normalized = normalize_damage_text(text)
        return bool(normalized) and normalized[-1:].isdigit() and parse_damage_value(normalized) is not None

    def _find_adjacent_suffix_hint(
        self,
        target_group: GroupedCandidate,
        grouped_candidates: list[GroupedCandidate],
        read_group_text: callable,
    ) -> str | None:
        """Find adjacent suffix token (K, M, B) near the target group."""
        best_hint: str | None = None
        best_gap: int | None = None

        for candidate in grouped_candidates:
            if candidate == target_group:
                continue
            if candidate.left <= target_group.right:
                continue
            if candidate.width > self.config.suffix_max_width or candidate.height > self.config.suffix_max_height:
                continue

            gap = candidate.left - target_group.right - 1
            if gap > self.config.suffix_max_gap:
                continue

            target_center_y = (target_group.top + target_group.bottom) / 2
            candidate_center_y = (candidate.top + candidate.bottom) / 2
            max_height = max(target_group.height, candidate.height)
            if abs(target_center_y - candidate_center_y) > max_height * self.config.suffix_max_vertical_drift:
                continue

            suffix_text = normalize_damage_text(read_group_text(candidate))
            if suffix_text not in {"K", "M", "B"}:
                continue

            if best_gap is None or gap < best_gap:
                best_gap = gap
                best_hint = suffix_text

        return best_hint

    def _is_ocr_ready_line(self, grouped: GroupedCandidate) -> bool:
        """Check if a grouped candidate is ready for OCR."""
        return (
            self._score_line_candidate(grouped) >= 5.0  # tight: each OCR call = 320ms
            and 12 <= grouped.width <= 380
            and 10 <= grouped.height <= 130
            and grouped.member_count >= 1
        )

    def _score_line_candidate(self, grouped: GroupedCandidate) -> float:
        """Score a line candidate for OCR readiness."""
        area = max(grouped.width * grouped.height, 1)
        fill_ratio = grouped.pixel_count / area
        aspect_ratio = grouped.width / max(grouped.height, 1)

        score = 0.0
        if 24 <= grouped.width <= 260:
            score += 3.0
        if 12 <= grouped.height <= 150:
            score += 3.0
        if 1.5 <= aspect_ratio <= 5.0:
            score += 2.0
        if 2 <= grouped.member_count <= 6:
            score += 2.0
        if 0.15 <= fill_ratio <= 0.7:
            score += 2.0

        if grouped.member_count == 1:
            score -= 3.0
        if grouped.width > 280:
            score -= 2.5
        if grouped.height > 160:
            score -= 2.5
        if fill_ratio > 0.75:
            score -= 2.0

        return score

    def _score_ocr_result(
        self,
        raw_text: str,
        parsed_value: int | None,
        line_score: float,
        member_count: int,
        width: int,
        height: int,
        pixel_count: int,
    ) -> float:
        """Score OCR result confidence using ML classifier.

        Args:
            raw_text: Raw OCR text.
            parsed_value: Parsed damage value.
            line_score: Heuristic line score.
            member_count: Number of connected components.
            width: Bounding box width.
            height: Bounding box height.
            pixel_count: Number of text pixels.

        Returns:
            ML-predicted confidence score (0.0 to 1.0).
        """
        # Extract features for ML classifier
        features = ConfidenceFeatures.from_candidate(
            line_score=line_score,
            member_count=member_count,
            width=width,
            height=height,
            pixel_count=pixel_count,
            raw_text=raw_text,
        )
        
        # Get ML prediction
        prediction = self.confidence_classifier.predict(features)
        
        return prediction.confidence
