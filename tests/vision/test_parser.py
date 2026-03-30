"""Tests for damage value parsing and plausibility checks.

Covers the two main bug classes fixed:
  1. Comma-formatted numbers with suffix (e.g. "1,000K" → 1_000_000)
  2. Multi-hit detection logic (plausibility gate accepting valid forms)
"""
import pytest

from d4v.vision.classifier import (
    is_plausible_damage_text,
    normalize_damage_text,
    parse_damage_value,
)


# ---------------------------------------------------------------------------
# normalize_damage_text
# ---------------------------------------------------------------------------

class TestNormalizeDamageText:
    def test_plain_number(self):
        assert normalize_damage_text("1234") == "1234"

    def test_k_suffix(self):
        assert normalize_damage_text("246k") == "246K"

    def test_m_suffix(self):
        assert normalize_damage_text("10.3M") == "10.3M"

    def test_b_suffix(self):
        assert normalize_damage_text("2b") == "2B"

    def test_comma_thousands_with_k(self):
        # "1,000K" → strips comma → "1000K"
        assert normalize_damage_text("1,000K") == "1000K"

    def test_comma_thousands_with_m(self):
        assert normalize_damage_text("1,234M") == "1234M"

    def test_comma_decimal_with_k(self):
        # "1,5K" (1-2 decimal digits after comma) → treated as "1.5K"
        assert normalize_damage_text("1,5K") == "1.5K"

    def test_whitespace_stripped(self):
        assert normalize_damage_text("  50K  ") == "50K"

    def test_empty(self):
        assert normalize_damage_text("") == ""


# ---------------------------------------------------------------------------
# parse_damage_value
# ---------------------------------------------------------------------------

class TestParseDamageValue:
    @pytest.mark.parametrize("text, expected", [
        ("246k",     246_000),
        ("246K",     246_000),
        ("10.3M",    10_300_000),
        ("2B",       2_000_000_000),
        ("1,000K",   1_000_000),     # BUG FIX: was returning 1000 before
        ("1,234M",   1_234_000_000),
        ("500",      500),
        ("1234",     1234),
        ("75",       75),            # small hit — valid since we widened regex
    ])
    def test_valid_values(self, text: str, expected: int):
        assert parse_damage_value(text) == expected

    @pytest.mark.parametrize("text", [
        "",
        "abc",
        "K",
        ".",
        "1.2.3K",
    ])
    def test_invalid_returns_none(self, text: str):
        assert parse_damage_value(text) is None


# ---------------------------------------------------------------------------
# is_plausible_damage_text
# ---------------------------------------------------------------------------

class TestIsPlausibleDamageText:
    @pytest.mark.parametrize("text", [
        "246K",
        "10.3M",
        "2B",
        "1,000K",    # BUG FIX: must be accepted as plausible
        "1,234M",    # BUG FIX: must be accepted as plausible
        "1234",
        "500",
        "75",        # small hit
        "99",        # small hit
    ])
    def test_plausible(self, text: str):
        assert is_plausible_damage_text(text) is True

    @pytest.mark.parametrize("text", [
        "",
        "abc",
        "K",
        "1",         # single digit — too small to be a hit
        "1,23",      # ambiguous decimal (no suffix, 2 chars after comma)
        "0",
        "0K",
    ])
    def test_not_plausible(self, text: str):
        assert is_plausible_damage_text(text) is False
