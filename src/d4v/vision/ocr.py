from __future__ import annotations

import os
import re

import cv2
import numpy as np
import pytesseract
from PIL import Image

from d4v.vision.classifier import parse_damage_value


_OCR_NOISE_RE = re.compile(r"[^0-9kKmMbB,.\-]")


def _configure_tesseract() -> None:
    """Apply TESSERACT_CMD env-var if set (pytesseract honours it natively)."""
    env_path = os.environ.get("TESSERACT_CMD")
    if env_path:
        pytesseract.pytesseract.tesseract_cmd = env_path


_configure_tesseract()


# ---------------------------------------------------------------------------
# Public API — signatures unchanged from the subprocess-based version
# ---------------------------------------------------------------------------


def ocr_image(
    image_path: "os.PathLike[str] | str",
    psm_modes: tuple[int, ...] = (8, 7, 13),
    whitelist: str = "0123456789.,kKmMbB",
) -> str:
    with Image.open(image_path) as image:
        return ocr_pil_image(image, psm_modes=psm_modes, whitelist=whitelist)


def ocr_pil_image(
    image: Image.Image,
    psm_modes: tuple[int, ...] = (8, 7, 13),
    whitelist: str = "0123456789.,kKmMbB",
) -> str:
    """Run OCR on a PIL image with fallback PSM modes."""
    # Configure Tesseract path on every call (handles env var changes)
    _configure_tesseract()
    
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
# Image preparation (OpenCV-based, replaces PIL pipeline)
# ---------------------------------------------------------------------------


def prepare_image_object_for_ocr(image: Image.Image) -> Image.Image:
    """
    Upscale, dilate, and binarise a grayscale mask image for Tesseract.

    Steps:
      1. Convert to grayscale numpy array.
      2. Upscale 6× with NEAREST (preserve hard digit edges).
      3. Dilate with a 3×3 kernel (equivalent to PIL MaxFilter(3)).
      4. Binary threshold — any non-zero pixel → 255.
      5. Convert back to PIL "L".
    """
    gray = np.array(image.convert("L"))
    h, w = gray.shape
    upscaled = cv2.resize(gray, (w * 6, h * 6), interpolation=cv2.INTER_NEAREST)
    kernel = np.ones((3, 3), np.uint8)
    dilated = cv2.dilate(upscaled, kernel, iterations=1)
    _, binary = cv2.threshold(dilated, 0, 255, cv2.THRESH_BINARY)
    return Image.fromarray(binary, mode="L")


# ---------------------------------------------------------------------------
# Text post-processing helpers (unchanged logic)
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
