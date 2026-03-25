from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import tempfile

from PIL import Image, ImageFilter

from d4v.vision.classifier import parse_damage_value


DEFAULT_TESSERACT_PATHS = (
    Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
)

_OCR_NOISE_RE = re.compile(r"[^0-9kKmMbB,.\-]")


def resolve_tesseract_path() -> Path:
    env_path = os.environ.get("TESSERACT_CMD")
    if env_path:
        path = Path(env_path)
        if path.exists():
            return path

    for path in DEFAULT_TESSERACT_PATHS:
        if path.exists():
            return path

    raise FileNotFoundError("Tesseract executable not found. Set TESSERACT_CMD if needed.")


def ocr_image(
    image_path: Path,
    psm_modes: tuple[int, ...] = (8, 7, 13),
    whitelist: str = "0123456789.,kKmMbB",
) -> str:
    prepared_image_path = prepare_image_for_ocr(image_path)
    return _ocr_prepared_image(
        prepared_image_path,
        psm_modes=psm_modes,
        whitelist=whitelist,
    )


def ocr_pil_image(
    image: Image.Image,
    psm_modes: tuple[int, ...] = (8, 7, 13),
    whitelist: str = "0123456789.,kKmMbB",
) -> str:
    prepared_image_path = prepare_image_object_for_ocr(image)
    return _ocr_prepared_image(
        prepared_image_path,
        psm_modes=psm_modes,
        whitelist=whitelist,
    )


def _ocr_prepared_image(
    prepared_image_path: Path,
    psm_modes: tuple[int, ...],
    whitelist: str,
) -> str:
    tesseract_path = resolve_tesseract_path()
    try:
        candidates: list[str] = []
        for psm in psm_modes:
            command = [
                str(tesseract_path),
                str(prepared_image_path),
                "stdout",
                "--psm",
                str(psm),
                "-l",
                "eng",
                "-c",
                f"tessedit_char_whitelist={whitelist}",
            ]
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=15,
            )
            if result.returncode != 0:
                continue
            candidates.append(clean_ocr_text(result.stdout))

        return choose_best_ocr_candidate(candidates)
    finally:
        if prepared_image_path.exists():
            prepared_image_path.unlink()


def prepare_image_for_ocr(image_path: Path) -> Path:
    with Image.open(image_path) as image:
        return prepare_image_object_for_ocr(image)


def prepare_image_object_for_ocr(image: Image.Image) -> Path:
    prepared = image.convert("L")
    prepared = prepared.resize(
        (prepared.width * 6, prepared.height * 6),
        Image.Resampling.NEAREST,
    )
    prepared = prepared.filter(ImageFilter.MaxFilter(3))
    prepared = prepared.point(lambda value: 255 if value > 0 else 0, mode="1").convert("L")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as handle:
        temp_path = Path(handle.name)
    prepared.save(temp_path)
    return temp_path


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
