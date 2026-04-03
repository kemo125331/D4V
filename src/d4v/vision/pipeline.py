"""Protocol interfaces and CombatTextPipeline service.

Defines abstract interfaces for testability and the main vision pipeline service.
"""

from __future__ import annotations

import concurrent.futures
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol, runtime_checkable

import PIL.ImageOps
from PIL import Image

from d4v.vision.classifier import (
    is_plausible_damage_text,
    normalize_damage_text,
    parse_damage_value,
)
from d4v.vision.color_mask import build_combat_text_mask
from d4v.vision.config import VisionConfig
from d4v.vision.grouping import GroupedCandidate, group_bounding_boxes
from d4v.vision.ocr import ocr_pil_image
from d4v.vision.segments import segment_damage_tokens
from d4v.vision.confidence_model import ConfidenceClassifier, ConfidenceFeatures
from d4v.runtime_paths import bundled_models_dir

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
            model_path = bundled_models_dir() / "confidence_model.joblib"

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
        # OCR upscaling compensates for the reduced processing size.
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
        # WinOCR is fast enough that parallel candidate OCR stays inexpensive.
        # Persistent pool still saves per-frame scheduling overhead.
        def _ocr_group(grouped: GroupedCandidate) -> tuple[GroupedCandidate, str]:
            pad = self.config.ocr_border
            left = max(0, grouped.left - pad)
            top_ = max(0, grouped.top - pad)
            right = min(crop.width, grouped.right + pad + 1)
            bottom = min(crop.height, grouped.bottom + pad + 1)

            # Mask crop for OCR-ready monochrome text
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
        all_ocr_targets = list(
            {
                id(g): g
                for g in ranked_lines
                + [g for g in grouped_candidates if g not in ranked_lines]
            }.values()
        )

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

            parsed_value = (
                parse_damage_value(normalized_text) if normalized_text else None
            )
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
        return (
            bool(normalized)
            and normalized[-1:].isdigit()
            and parse_damage_value(normalized) is not None
        )

    def _find_adjacent_suffix_hint(
        self,
        target_group: GroupedCandidate,
        grouped_candidates: list[GroupedCandidate],
        read_group_text: Callable[[GroupedCandidate], str],
    ) -> str | None:
        """Find adjacent suffix token (K, M, B) near the target group."""
        best_hint: str | None = None
        best_gap: int | None = None

        for candidate in grouped_candidates:
            if candidate == target_group:
                continue
            if candidate.left <= target_group.right:
                continue
            if (
                candidate.width > self.config.suffix_max_width
                or candidate.height > self.config.suffix_max_height
            ):
                continue

            gap = candidate.left - target_group.right - 1
            if gap > self.config.suffix_max_gap:
                continue

            target_center_y = (target_group.top + target_group.bottom) / 2
            candidate_center_y = (candidate.top + candidate.bottom) / 2
            max_height = max(target_group.height, candidate.height)
            if (
                abs(target_center_y - candidate_center_y)
                > max_height * self.config.suffix_max_vertical_drift
            ):
                continue

            suffix_text = normalize_damage_text(read_group_text(candidate))
            if suffix_text not in {"K", "M", "B"}:
                continue

            if best_gap is None or gap < best_gap:
                best_gap = gap
                best_hint = suffix_text

        return best_hint

    def _is_ocr_ready_line(self, grouped: GroupedCandidate) -> bool:
        """Check if a grouped candidate is ready for OCR.
        
        Thresholds tuned to minimize OCR calls (each ~320ms) while catching
        valid damage numbers.
        """
        return (
            self._score_line_candidate(grouped) >= 5.0  # Minimum score threshold
            and 12 <= grouped.width <= 380  # Min/max width at 1080p
            and 10 <= grouped.height <= 130  # Min/max height at 1080p
            and grouped.member_count >= 1
        )

    def _score_line_candidate(self, grouped: GroupedCandidate) -> float:
        """Score a line candidate for OCR readiness.
        
        Scoring system based on damage number characteristics at 1080p resolution
        after downscaling to 1280px max width.
        
        Positive scores (OCR-ready characteristics):
        - Width 24-260px: Typical damage number width range
        - Height 12-150px: Typical damage number height range
        - Aspect ratio 1.5-5.0: Horizontal text orientation
        - Member count 2-6: Multiple connected components (good segmentation)
        - Fill ratio 0.15-0.7: Appropriate text density
        
        Negative scores (likely false positives):
        - Single component: Likely noise or UI element
        - Width >280px: Too wide, likely UI element
        - Height >160px: Too tall, likely UI element
        - Fill ratio >0.75: Too dense, likely solid UI block
        """
        area = max(grouped.width * grouped.height, 1)
        fill_ratio = grouped.pixel_count / area
        aspect_ratio = grouped.width / max(grouped.height, 1)

        score = 0.0
        
        # Positive scores (OCR-ready characteristics)
        if 24 <= grouped.width <= 260:  # Typical damage number width
            score += 3.0
        if 12 <= grouped.height <= 150:  # Typical damage number height
            score += 3.0
        if 1.5 <= aspect_ratio <= 5.0:  # Horizontal text orientation
            score += 2.0
        if 2 <= grouped.member_count <= 6:  # Good segmentation
            score += 2.0
        if 0.15 <= fill_ratio <= 0.7:  # Appropriate text density
            score += 2.0

        # Negative scores (likely false positives)
        if grouped.member_count == 1:  # Single component = likely noise
            score -= 3.0
        if grouped.width > 280:  # Too wide = UI element
            score -= 2.5
        if grouped.height > 160:  # Too tall = UI element
            score -= 2.5
        if fill_ratio > 0.75:  # Too dense = solid block
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


# =============================================================================
# Multi-Frame Voting Extension (Optional)
# =============================================================================
# Integrates OCR voting across frames for improved accuracy.
# Disabled by default - import from d4v.experimental for full features.
# =============================================================================


@dataclass(frozen=True)
class VotingDetectedHit(DetectedHit):
    """Detected hit with multi-frame voting information.

    Extends DetectedHit with voting metadata.

    Attributes:
        vote_count: Number of frames that agreed on this hit.
        total_votes: Total frames where this hit was tracked.
        agreement_ratio: Ratio of agreeing votes (0.0-1.0).
    """

    vote_count: int = 1
    total_votes: int = 1
    agreement_ratio: float = 1.0


class CombatTextPipelineWithVoting:
    """Combat text pipeline with multi-frame OCR voting.

    Wraps CombatTextPipeline to add voting-based accuracy improvements.
    Tracks damage numbers across multiple frames and uses weighted voting
    to determine the most likely value.

    Example:
        pipeline = CombatTextPipelineWithVoting(
            base_pipeline=pipeline,
            spatial_threshold=70.0,      # Pixel distance for grouping
            frame_window=5,              # Frames to track
            min_votes=2,                 # Minimum votes for confidence boost
        )

        hits = pipeline.process_image(image, frame_index=100, timestamp_ms=3333)
    """

    def __init__(
        self,
        base_pipeline: CombatTextPipeline,
        spatial_threshold: float = 70.0,
        frame_window: int = 5,
        min_votes: int = 2,
        value_tolerance: float = 0.05,
        confidence_boost: float = 0.15,
    ) -> None:
        """Initialize voting pipeline.

        Args:
            base_pipeline: Base CombatTextPipeline to wrap.
            spatial_threshold: Max pixel distance for vote grouping.
            frame_window: Max frame span for vote grouping.
            min_votes: Minimum votes for confidence boost.
            value_tolerance: Value matching tolerance (fraction).
            confidence_boost: Confidence boost for multi-frame hits.
        """
        self.base_pipeline = base_pipeline
        self.spatial_threshold = spatial_threshold
        self.frame_window = frame_window
        self.min_votes = min_votes
        self.value_tolerance = value_tolerance
        self.confidence_boost = confidence_boost

        # Vote tracking
        self._votes: list[dict] = []
        self._tracks: dict[int, list[dict]] = {}
        self._next_track_id = 1

    def process_image(
        self,
        image: Image.Image,
        frame_index: int,
        timestamp_ms: int,
    ) -> list[VotingDetectedHit]:
        """Process image with multi-frame voting.

        Args:
            image: Input image.
            frame_index: Frame index.
            timestamp_ms: Timestamp in milliseconds.

        Returns:
            List of VotingDetectedHit with voting metadata.
        """
        # Get base detections
        base_hits = self.base_pipeline.process_image(
            image=image,
            frame_index=frame_index,
            timestamp_ms=timestamp_ms,
        )

        # Convert to vote format
        for hit in base_hits:
            vote = {
                "frame_index": frame_index,
                "parsed_value": hit.parsed_value,
                "confidence": hit.confidence,
                "center_x": hit.center_x,
                "center_y": hit.center_y,
                "raw_text": hit.sample_text,
            }
            self._add_vote(vote)

        # Aggregate votes and apply confidence boosts
        return self._apply_voting(frame_index)

    def _add_vote(self, vote: dict) -> None:
        """Add a vote and try to assign to existing track.

        Args:
            vote: Vote dictionary.
        """
        self._votes.append(vote)

        # Find matching track
        track_id = self._find_matching_track(vote)

        if track_id is None:
            # Create new track
            track_id = self._next_track_id
            self._next_track_id += 1
            self._tracks[track_id] = []

        self._tracks[track_id].append(vote)

    def _find_matching_track(self, vote: dict) -> int | None:
        """Find existing track matching this vote.

        Args:
            vote: Vote to match.

        Returns:
            Track ID or None.
        """
        for track_id, track_votes in self._tracks.items():
            if not track_votes:
                continue

            last_vote = track_votes[-1]

            # Check frame window
            if vote["frame_index"] - last_vote["frame_index"] > self.frame_window:
                continue

            # Check spatial proximity
            dx = vote["center_x"] - last_vote["center_x"]
            dy = vote["center_y"] - last_vote["center_y"]
            distance = (dx ** 2 + dy ** 2) ** 0.5

            if distance > self.spatial_threshold:
                continue

            # Check value similarity
            if last_vote["parsed_value"] > 0:
                value_diff = abs(
                    vote["parsed_value"] - last_vote["parsed_value"]
                ) / last_vote["parsed_value"]
                if value_diff > self.value_tolerance:
                    continue

            return track_id

        return None

    def _apply_voting(
        self,
        current_frame: int,
    ) -> list[VotingDetectedHit]:
        """Apply voting to current frame detections.

        Args:
            current_frame: Current frame index.

        Returns:
            List of VotingDetectedHit with boosted confidence.
        """
        hits: list[VotingDetectedHit] = []

        # Process active tracks
        for track_id, track_votes in self._tracks.items():
            # Filter to recent votes
            recent_votes = [
                v
                for v in track_votes
                if current_frame - v["frame_index"] <= self.frame_window
            ]

            if not recent_votes:
                continue

            # Get best vote (highest confidence)
            best_vote = max(recent_votes, key=lambda v: v["confidence"])

            # Calculate voting metrics
            vote_count = len(recent_votes)
            total_votes = len(track_votes)
            agreement_ratio = vote_count / max(total_votes, 1)

            # Apply confidence boost for multi-frame confirmation
            base_confidence = best_vote["confidence"]
            if vote_count >= self.min_votes:
                boosted_confidence = min(
                    base_confidence + self.confidence_boost, 1.0
                )
            else:
                boosted_confidence = base_confidence

            hits.append(
                VotingDetectedHit(
                    frame_index=best_vote["frame_index"],
                    timestamp_ms=best_vote.get("timestamp_ms"),
                    parsed_value=best_vote["parsed_value"],
                    confidence=boosted_confidence,
                    sample_text=best_vote["raw_text"],
                    center_x=best_vote["center_x"],
                    center_y=best_vote["center_y"],
                    vote_count=vote_count,
                    total_votes=total_votes,
                    agreement_ratio=agreement_ratio,
                )
            )

        # Prune old tracks
        self._prune_old_tracks(current_frame)

        return hits

    def _prune_old_tracks(self, current_frame: int, max_age: int = 10) -> None:
        """Remove tracks that haven't been updated recently.

        Args:
            current_frame: Current frame index.
            max_age: Maximum frames since last update.
        """
        to_remove = [
            track_id
            for track_id, track_votes in self._tracks.items()
            if current_frame - track_votes[-1]["frame_index"] > max_age
        ]

        for track_id in to_remove:
            del self._tracks[track_id]

    def reset(self) -> None:
        """Reset voting state."""
        self._votes.clear()
        self._tracks.clear()
        self._next_track_id = 1
