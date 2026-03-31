"""OCR module — WinOCR-only damage text recognition.

WinOCR (Windows.Media.Ocr) is the only supported OCR engine in this
project. The public API remains unchanged so the rest of the pipeline
does not need to know which OCR backend is in use.
"""

from __future__ import annotations

import re
from PIL import Image

from d4v.vision.classifier import parse_damage_value

_OCR_NOISE_RE = re.compile(r"[^0-9kKmMbB,.\-]")

# Try to import WinOCR; gracefully fall back if unavailable.
_HAS_WINOCR = False
try:
    from winocr import recognize_pil_sync as _winocr_recognize  # noqa: F401

    _HAS_WINOCR = True
except ImportError:
    _winocr_recognize = None  # type: ignore[assignment]


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
    """Run OCR on a mask image with WinOCR.

    Args:
        image: Binary/grayscale mask crop of the candidate region.
        psm_modes: Unused. Kept for API compatibility.
        whitelist: Allowed characters.
        rgb_source: Optional original RGB crop (same region). If provided,
            WinOCR uses this instead of the mask — it performs much better
            on natural-looking coloured text.

    Returns:
        Best OCR text found, cleaned and scored.
    """
    if _HAS_WINOCR:
        return _run_winocr(image, rgb_source=rgb_source)

    return ""


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
        padded_rgb = Image.new(
            "RGB", (rgb_up.width + 20, rgb_up.height + 20), (0, 0, 0)
        )
        padded_rgb.paste(rgb_up, (10, 10))
        try:
            r = _winocr_recognize(padded_rgb, lang="en")
            text = clean_ocr_text(r.get("text", ""))
            if text:
                candidates.append(text)
        except Exception:
            pass

    return choose_best_ocr_candidate(candidates)


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
