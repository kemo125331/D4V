"""OCR module — WinOCR primary engine with Tesseract fallback.

WinOCR (Windows.Media.Ocr) runs at 1-15ms per call via the built-in
Windows Runtime OCR engine.  Tesseract is kept as a fallback for cases
where WinOCR returns nothing (e.g. very small crops, unusual glyphs).

The public API (`ocr_pil_image`) is unchanged — callers don't need to
know which engine produced the result.
"""
from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING

import cv2
import numpy as np
import pytesseract
from PIL import Image

from d4v.vision.classifier import parse_damage_value

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Startup configuration
# ---------------------------------------------------------------------------

_OCR_NOISE_RE = re.compile(r"[^0-9kKmMbB,.\-]")


def _configure_tesseract() -> None:
    """Apply TESSERACT_CMD env-var if set (pytesseract honours it natively)."""
    env_path = os.environ.get("TESSERACT_CMD")
    if env_path:
        pytesseract.pytesseract.tesseract_cmd = env_path


_configure_tesseract()

# Try to import WinOCR; gracefully fall back if unavailable.
_HAS_WINOCR = False
try:
    from winocr import recognize_pil_sync as _winocr_recognize  # noqa: F401

    _HAS_WINOCR = True
except ImportError:
    _winocr_recognize = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def ocr_image(
    image_path: "os.PathLike[str] | str",
    psm_modes: tuple[int, ...] = (7,),
    whitelist: str = "0123456789.,kKmMbB",
) -> str:
    with Image.open(image_path) as image:
        return ocr_pil_image(image, psm_modes=psm_modes, whitelist=whitelist)


def ocr_pil_image(
    image: Image.Image,
    psm_modes: tuple[int, ...] = (7,),
    whitelist: str = "0123456789.,kKmMbB",
    *,
    rgb_source: Image.Image | None = None,
) -> str:
    """Run OCR on a mask image, trying WinOCR first, then Tesseract.

    Args:
        image: Binary/grayscale mask crop of the candidate region.
        psm_modes: Tesseract PSM modes (fallback only).
        whitelist: Allowed characters.
        rgb_source: Optional original RGB crop (same region). If provided,
            WinOCR uses this instead of the mask — it performs much better
            on natural-looking coloured text.

    Returns:
        Best OCR text found, cleaned and scored.
    """
    # --- WinOCR path (fast: 1-15ms) ----------------------------------------
    if _HAS_WINOCR:
        result = _run_winocr(image, rgb_source=rgb_source)
        if result:
            return result
    # --- Tesseract fallback (slow: 120-300ms) ------------------------------
    return _run_tesseract(image, psm_modes=psm_modes, whitelist=whitelist)


# ---------------------------------------------------------------------------
# WinOCR engine
# ---------------------------------------------------------------------------


def _run_winocr(
    mask_image: Image.Image,
    *,
    rgb_source: Image.Image | None = None,
) -> str:
    """Try Windows native OCR on the candidate crop.

    Strategy: prepare multiple image variants and pick the best result.
      1. Upscaled inverted mask (black text on white — OCR's favourite)
      2. Upscaled RGB source (if available)
      3. Upscaled mask as-is
    """
    if _winocr_recognize is None:
        return ""

    candidates: list[str] = []

    # --- Variant 1: inverted mask, upscaled --------------------------------
    # WinOCR strongly prefers dark text on light background.
    gray = mask_image.convert("L")
    w, h = gray.size
    # Upscale 4× so text is large enough for WinOCR's neural model
    scale_factor = max(4, 120 // max(h, 1))  # ensure at least 120px tall
    up = gray.resize((w * scale_factor, h * scale_factor), Image.NEAREST)
    # Invert: white text → black text on white background
    inv = Image.eval(up, lambda px: 255 - px)
    # Add white padding
    padded = Image.new("L", (inv.width + 20, inv.height + 20), 255)
    padded.paste(inv, (10, 10))
    try:
        r = _winocr_recognize(padded.convert("RGB"), lang="en")
        text = clean_ocr_text(r.get("text", ""))
        if text:
            candidates.append(text)
    except Exception:
        pass

    # --- Variant 2: RGB source, upscaled -----------------------------------
    if rgb_source is not None:
        w2, h2 = rgb_source.size
        sf2 = max(4, 120 // max(h2, 1))
        rgb_up = rgb_source.resize((w2 * sf2, h2 * sf2), Image.NEAREST)
        # Add padding
        padded_rgb = Image.new("RGB", (rgb_up.width + 20, rgb_up.height + 20), (0, 0, 0))
        padded_rgb.paste(rgb_up, (10, 10))
        try:
            r = _winocr_recognize(padded_rgb, lang="en")
            text = clean_ocr_text(r.get("text", ""))
            if text:
                candidates.append(text)
        except Exception:
            pass

    return choose_best_ocr_candidate(candidates)


# ---------------------------------------------------------------------------
# Tesseract engine (fallback)
# ---------------------------------------------------------------------------


def _run_tesseract(
    image: Image.Image,
    psm_modes: tuple[int, ...] = (7,),
    whitelist: str = "0123456789.,kKmMbB",
) -> str:
    """Run Tesseract OCR — the slow but reliable fallback."""
    prepared = prepare_image_object_for_ocr(image)
    candidates: list[str] = []
    for psm in psm_modes:
        config = f"--psm {psm} --oem 3 -c tessedit_char_whitelist={whitelist}"
        try:
            raw = pytesseract.image_to_string(prepared, config=config)
            candidates.append(clean_ocr_text(raw))
        except pytesseract.TesseractNotFoundError as exc:
            raise FileNotFoundError(
                "Tesseract executable not found. Install Tesseract and set "
                "the TESSERACT_CMD env-var if needed."
            ) from exc
        except Exception:
            continue

    return choose_best_ocr_candidate(candidates)


# ---------------------------------------------------------------------------
# Image preparation (OpenCV-based, for Tesseract)
# ---------------------------------------------------------------------------


def prepare_image_object_for_ocr(image: Image.Image) -> Image.Image:
    """
    Upscale, dilate, and binarise a grayscale mask image for Tesseract.

    Steps:
      1. Convert to grayscale numpy array.
      2. Upscale 4× with NEAREST (preserve hard digit edges).
      3. Dilate with a 3×3 kernel (equivalent to PIL MaxFilter(3)).
      4. Binary threshold — any non-zero pixel → 255.
      5. Convert back to PIL "L".
    """
    gray = np.array(image.convert("L"))
    h, w = gray.shape
    upscaled = cv2.resize(gray, (w * 4, h * 4), interpolation=cv2.INTER_NEAREST)
    kernel = np.ones((3, 3), np.uint8)
    dilated = cv2.dilate(upscaled, kernel, iterations=1)
    _, binary = cv2.threshold(dilated, 0, 255, cv2.THRESH_BINARY)
    return Image.fromarray(binary, mode="L")


# ---------------------------------------------------------------------------
# Text post-processing helpers
# ---------------------------------------------------------------------------


def clean_ocr_text(text: str) -> str:
    normalized = text.strip()
    normalized = normalized.replace(" ", "")
    normalized = normalized.replace("\n", "")
    normalized = normalized.replace("O", "0").replace("o", "0")
    normalized = normalized.replace("S", "5")
    normalized = _OCR_NOISE_RE.sub("", normalized)
    return normalized


def choose_best_ocr_candidate(candidates: list[str]) -> str:
    best = ""
    best_score = float("-inf")
    for candidate in candidates:
        score = score_ocr_candidate(candidate)
        if score > best_score:
            best = candidate
            best_score = score
    return best


def score_ocr_candidate(text: str) -> float:
    if not text:
        return -10.0

    score = 0.0
    parsed_value = parse_damage_value(text)
    if parsed_value is not None:
        score += 10.0

    if any(char.isdigit() for char in text):
        score += 3.0
    if any(char in "kKmMbB" for char in text):
        score += 1.5
    if "." in text or "," in text:
        score += 1.0

    if len(text) < 2:
        score -= 3.0
    if len(text) > 10:
        score -= 2.0

    return score
