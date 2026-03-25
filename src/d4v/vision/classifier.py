import re
from dataclasses import dataclass

from d4v.domain.models import FloatingTextCandidate, FloatingTextKind

_DAMAGE_TEXT_RE = re.compile(r"^\d[\d,]*(?:\.\d+)?[kmb]?$", re.IGNORECASE)
_PLAUSIBLE_SUFFIXED_DAMAGE_RE = re.compile(r"^\d{1,5}(?:\.\d{1,3})?[KMB]$")
_PLAUSIBLE_PLAIN_DAMAGE_RE = re.compile(r"^\d{3,10}$")


@dataclass(frozen=True)
class ClassifiedText:
    text: str
    kind: FloatingTextKind
    parsed_damage: int | None = None


def classify_text(candidate: FloatingTextCandidate) -> ClassifiedText:
    normalized = candidate.text.strip()
    lowered = normalized.casefold()

    if not normalized:
        return ClassifiedText(text=candidate.text, kind=FloatingTextKind.UNKNOWN)

    if "gold" in lowered:
        return ClassifiedText(text=candidate.text, kind=FloatingTextKind.GOLD)

    if _DAMAGE_TEXT_RE.fullmatch(normalized):
        return ClassifiedText(
            text=candidate.text,
            kind=FloatingTextKind.DAMAGE,
            parsed_damage=parse_damage_value(normalized),
        )

    if any(char.isalpha() for char in normalized):
        return ClassifiedText(text=candidate.text, kind=FloatingTextKind.ITEM)

    return ClassifiedText(text=candidate.text, kind=FloatingTextKind.UNKNOWN)


def parse_damage_value(text: str) -> int | None:
    normalized = normalize_damage_text(text)
    if not _DAMAGE_TEXT_RE.fullmatch(normalized):
        return None

    multiplier = 1
    suffix = normalized[-1].casefold()
    if suffix == "k":
        multiplier = 1_000
        normalized = normalized[:-1]
    elif suffix == "m":
        multiplier = 1_000_000
        normalized = normalized[:-1]
    elif suffix == "b":
        multiplier = 1_000_000_000
        normalized = normalized[:-1]

    return int(float(normalized) * multiplier)


def normalize_damage_text(text: str) -> str:
    normalized = text.strip().replace(" ", "")
    if not normalized:
        return normalized

    suffix = ""
    body = normalized
    if normalized[-1].isalpha():
        suffix = normalized[-1].upper()
        body = normalized[:-1]

    if "," in body and "." not in body:
        parts = body.split(",")
        if suffix and len(parts) == 2 and 1 <= len(parts[1]) <= 2:
            body = ".".join(parts)
        else:
            body = "".join(parts)
    else:
        body = body.replace(",", "")

    return body + suffix


def is_plausible_damage_text(text: str) -> bool:
    original = text.strip().replace(" ", "")
    if not original:
        return False
    if not original[-1:].isalpha() and "," in original and "." not in original:
        parts = original.split(",")
        if len(parts) == 2 and 1 <= len(parts[1]) <= 2:
            return False

    normalized = normalize_damage_text(text)
    if not normalized:
        return False

    parsed_value = parse_damage_value(normalized)
    if parsed_value is None or parsed_value <= 0:
        return False

    if normalized[-1:].isalpha():
        return _PLAUSIBLE_SUFFIXED_DAMAGE_RE.fullmatch(normalized) is not None

    return _PLAUSIBLE_PLAIN_DAMAGE_RE.fullmatch(normalized) is not None
