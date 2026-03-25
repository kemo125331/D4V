from d4v.domain.models import FloatingTextCandidate, FloatingTextKind
from d4v.vision.classifier import classify_text, parse_damage_value


def test_classify_text_detects_damage():
    result = classify_text(FloatingTextCandidate(text="12,500", frame=1))
    assert result.kind == FloatingTextKind.DAMAGE
    assert result.parsed_damage == 12500


def test_classify_text_detects_abbreviated_damage():
    assert parse_damage_value("18.2K") == 18200


def test_classify_text_detects_million_suffix_damage():
    result = classify_text(FloatingTextCandidate(text="246m", frame=1))
    assert result.kind == FloatingTextKind.DAMAGE
    assert result.parsed_damage == 246_000_000


def test_classify_text_detects_gold():
    result = classify_text(FloatingTextCandidate(text="35 Gold", frame=1))
    assert result.kind == FloatingTextKind.GOLD


def test_classify_text_detects_item_text():
    result = classify_text(FloatingTextCandidate(text="Ancestral Legendary Helm", frame=1))
    assert result.kind == FloatingTextKind.ITEM
