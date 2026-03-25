import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from d4v.domain.models import FloatingTextCandidate, FloatingTextKind
from d4v.vision.classifier import classify_text


@dataclass(frozen=True)
class CandidateAnalysisSummary:
    total_candidates: int
    category_counts: dict[str, int]
    parsed_damage_total: int
    top_unknown_texts: list[str]


def load_candidates(path: Path) -> list[FloatingTextCandidate]:
    raw_items = json.loads(path.read_text(encoding="utf-8"))
    return [
        FloatingTextCandidate(
            text=item["text"],
            frame=item["frame"],
            timestamp_ms=item.get("timestamp_ms"),
            confidence=item.get("confidence", 0.0),
        )
        for item in raw_items
    ]


def analyze_candidates(candidates: list[FloatingTextCandidate]) -> CandidateAnalysisSummary:
    category_counts: Counter[str] = Counter()
    parsed_damage_total = 0
    unknown_texts: Counter[str] = Counter()

    for candidate in candidates:
        result = classify_text(candidate)
        category_counts[str(result.kind)] += 1
        if result.kind == FloatingTextKind.DAMAGE and result.parsed_damage is not None:
            parsed_damage_total += result.parsed_damage
        if result.kind == FloatingTextKind.UNKNOWN:
            unknown_texts[result.text] += 1

    return CandidateAnalysisSummary(
        total_candidates=len(candidates),
        category_counts=dict(category_counts),
        parsed_damage_total=parsed_damage_total,
        top_unknown_texts=[text for text, _count in unknown_texts.most_common(5)],
    )


def render_summary(summary: CandidateAnalysisSummary) -> str:
    lines = [
        f"Total candidates: {summary.total_candidates}",
        f"Parsed visible damage total: {summary.parsed_damage_total}",
        "Category counts:",
    ]
    for key in sorted(summary.category_counts):
        lines.append(f"- {key}: {summary.category_counts[key]}")

    if summary.top_unknown_texts:
        lines.append("Top unknown texts:")
        for text in summary.top_unknown_texts:
            lines.append(f"- {text}")

    return "\n".join(lines)


def main(path: str) -> int:
    summary = analyze_candidates(load_candidates(Path(path)))
    print(render_summary(summary))
    return 0
