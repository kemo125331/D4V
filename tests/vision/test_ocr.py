import pytest
from PIL import Image, ImageDraw

from d4v.vision.classifier import (
    is_plausible_damage_text,
    normalize_damage_text,
    parse_damage_value,
)
from d4v.vision.ocr import (
    choose_best_ocr_candidate,
    clean_ocr_text,
    score_ocr_candidate,
    ocr_pil_image,
)


def test_clean_ocr_text_keeps_damage_like_format():
    assert clean_ocr_text(" 45.6M \n") == "45.6M"


def test_clean_ocr_text_removes_noise():
    assert clean_ocr_text("A4S,6M?") == "45,6M"


def test_choose_best_ocr_candidate_prefers_parseable_damage():
    best = choose_best_ocr_candidate(["", "M", "45.6M", "m59"])
    assert best == "45.6M"


def test_score_ocr_candidate_penalizes_single_suffix():
    assert score_ocr_candidate("45.6M") > score_ocr_candidate("M")


def test_normalize_damage_text_converts_decimal_comma_with_suffix():
    assert normalize_damage_text("45,6m") == "45.6M"


def test_parse_damage_value_handles_decimal_comma_suffix():
    assert parse_damage_value("45,6M") == 45_600_000


def test_parse_damage_value_handles_suffix_scaling_examples():
    assert parse_damage_value("246k") == 246_000
    assert parse_damage_value("246K") == 246_000
    assert parse_damage_value("246m") == 246_000_000
    assert parse_damage_value("246M") == 246_000_000
    assert parse_damage_value("1.5b") == 1_500_000_000


def test_is_plausible_damage_text_rejects_implausible_suffix_shape():
    assert not is_plausible_damage_text("363500M")
    assert is_plausible_damage_text("248M")


def _make_digit_image(digit: str = "5", size: int = 36) -> Image.Image:
    img = Image.new("L", (size, size), color=0)
    draw = ImageDraw.Draw(img)
    draw.text((4, 4), digit, fill=255)
    return img


def test_ocr_pil_image_with_winocr_or_empty():
    result = ocr_pil_image(_make_digit_image("5"))
    assert "5" in result or result == ""
