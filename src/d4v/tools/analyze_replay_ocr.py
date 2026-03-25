from __future__ import annotations

import json
import math
from pathlib import Path
import re

from d4v.domain.models import StableDamageHit
from d4v.domain.replay_summary import build_replay_combat_summary
from d4v.tools.analyze_replay_tokens import extract_replay_tokens
from d4v.vision.classifier import is_plausible_damage_text, normalize_damage_text, parse_damage_value
from d4v.vision.ocr import ocr_image


def line_center(line: dict[str, object]) -> tuple[float, float]:
    return (
        (int(line["left"]) + int(line["right"])) / 2,
        (int(line["top"]) + int(line["bottom"])) / 2,
    )


def select_temporal_neighbor_lines(
    lines: list[dict[str, object]],
    max_candidates: int = 50,
    seed_count: int | None = None,
    frame_window: int = 2,
    center_distance_threshold: float = 80.0,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    enriched_lines: list[dict[str, object]] = []
    for line in lines:
        if not line["is_ocr_ready"]:
            continue
        enriched_lines.append(
            {
                **line,
                "frame_index": parse_frame_index(str(line["frame_name"])),
            }
        )

    def center_distance(first: dict[str, object], second: dict[str, object]) -> float:
        return math.dist(line_center(first), line_center(second))

    supported_lines: list[dict[str, object]] = []
    for line in enriched_lines:
        temporal_support = 0.0
        for neighbor in enriched_lines:
            if line["mask_name"] == neighbor["mask_name"]:
                continue
            frame_delta = abs(int(line["frame_index"]) - int(neighbor["frame_index"]))
            if frame_delta == 0 or frame_delta > frame_window:
                continue
            distance = center_distance(line, neighbor)
            if distance > center_distance_threshold:
                continue
            temporal_support += 1.0 - (distance / center_distance_threshold) * 0.5
        supported_lines.append(
            {
                **line,
                "temporal_support": temporal_support,
            }
        )

    ranked_seed_pool = sorted(
        supported_lines,
        key=lambda item: (
            -(float(item["score"]) + (float(item["temporal_support"]) * 1.5)),
            int(item["frame_index"]),
        ),
    )
    if seed_count is None:
        seed_count = min(max(12, len(ranked_seed_pool) // 4), 48)
    seed_lines = ranked_seed_pool[:seed_count]
    selected: dict[str, dict[str, object]] = {}

    for seed_priority, seed in enumerate(seed_lines):
        seed_center_x, seed_center_y = line_center(seed)
        seed_frame_index = int(seed["frame_index"])
        candidate_matches: dict[int, list[dict[str, object]]] = {}

        for line in supported_lines:
            frame_delta = abs(int(line["frame_index"]) - seed_frame_index)
            if frame_delta > frame_window:
                continue

            center_x, center_y = line_center(line)
            center_distance = math.dist((seed_center_x, seed_center_y), (center_x, center_y))
            if center_distance > center_distance_threshold:
                continue

            candidate_matches.setdefault(int(line["frame_index"]), []).append(
                {
                    **line,
                    "center_distance": center_distance,
                }
            )

        for frame_matches in candidate_matches.values():
            for frame_rank, line in enumerate(
                sorted(
                    frame_matches,
                    key=lambda item: (float(item["center_distance"]), -float(item["score"])),
                )[:2]
            ):
                frame_delta = abs(int(line["frame_index"]) - seed_frame_index)
                center_distance = float(line["center_distance"])
                selection_rank = (
                    (float(seed["score"]) * 2.0)
                    + (float(seed["temporal_support"]) * 1.5)
                    + float(line["score"])
                    + float(line["temporal_support"])
                    - (frame_delta * 0.75)
                    - (center_distance / center_distance_threshold)
                    - (frame_rank * 0.25)
                    - (seed_priority * 0.05)
                )
                existing = selected.get(str(line["mask_name"]))
                if existing is None or selection_rank > float(existing["selection_rank"]):
                    selected[str(line["mask_name"])] = {
                        **line,
                        "selection_rank": selection_rank,
                    }

    ranked_selection = sorted(
        selected.values(),
        key=lambda item: (
            -float(item["selection_rank"]),
            int(item["frame_index"]),
            -float(item["score"]),
        ),
    )
    trimmed_selection = ranked_selection[:max_candidates]
    return seed_lines, trimmed_selection


def analyze_replay_ocr(
    session_dir: Path,
    max_candidates: int = 50,
    top_frame_count: int | None = None,
    neighbor_radius: int = 2,
    seed_count: int | None = None,
    recent_frame_limit: int | None = None,
) -> dict[str, object]:
    metadata = load_replay_metadata(session_dir)
    token_summary = extract_replay_tokens(
        session_dir,
        top_frame_count=top_frame_count,
        neighbor_radius=neighbor_radius,
        recent_frame_limit=recent_frame_limit,
    )
    seed_lines, lines = select_temporal_neighbor_lines(
        token_summary["lines"],
        max_candidates=max_candidates,
        seed_count=seed_count,
    )

    results: list[dict[str, object]] = []
    for line in lines:
        mask_path = session_dir / "analysis" / "combat-lines" / line["mask_name"]
        raw_text = ocr_image(mask_path)
        normalized_text = normalize_damage_text(raw_text) if raw_text else ""
        parsed_value = parse_damage_value(normalized_text) if normalized_text else None
        confidence = score_ocr_result(
            raw_text=normalized_text,
            parsed_value=parsed_value,
            line_score=float(line["score"]),
            member_count=int(line["member_count"]),
            width=int(line["width"]),
            height=int(line["height"]),
        )
        frame_index = parse_frame_index(str(line["frame_name"]))
        results.append(
            {
                "frame_name": line["frame_name"],
                "frame_index": frame_index,
                "mask_name": line["mask_name"],
                "raw_text": raw_text,
                "normalized_text": normalized_text,
                "parsed_value": parsed_value,
                "score": line["score"],
                "confidence": confidence,
                "is_confident": confidence >= 0.6,
                "is_plausible": is_plausible_damage_text(normalized_text),
                "left": line["left"],
                "top": line["top"],
                "right": line["right"],
                "bottom": line["bottom"],
            }
        )

    stable_hits = dedupe_hits(results, replay_fps=metadata.get("fps"))
    replay_summary = build_replay_combat_summary(
        stable_hits,
        metadata,
        candidate_count=len(lines),
        recognized_count=sum(1 for item in results if item["raw_text"]),
        parsed_count=sum(1 for item in results if item["parsed_value"] is not None),
        confident_count=sum(1 for item in results if item["is_confident"]),
    )
    summary = {
        "session_dir": str(session_dir),
        "metadata": metadata,
        "seed_line_count": len(seed_lines),
        "candidate_count": len(lines),
        "recognized_count": sum(1 for item in results if item["raw_text"]),
        "parsed_count": sum(1 for item in results if item["parsed_value"] is not None),
        "confident_count": sum(1 for item in results if item["is_confident"]),
        "stable_hit_count": len(stable_hits),
        "repeated_hit_count": sum(1 for hit in stable_hits if hit.occurrences > 1),
        "max_occurrences": max((hit.occurrences for hit in stable_hits), default=0),
        "replay_summary": replay_summary.to_dict(),
        "results": results,
        "stable_hits": [
            {
                "frame_index": hit.frame_index,
                "timestamp_ms": hit.timestamp_ms,
                "parsed_value": hit.parsed_value,
                "first_frame": hit.first_frame,
                "last_frame": hit.last_frame,
                "occurrences": hit.occurrences,
                "best_confidence": hit.confidence,
                "sample_text": hit.sample_text,
                "center_x": hit.center_x,
                "center_y": hit.center_y,
            }
            for hit in stable_hits
        ],
    }
    output_dir = session_dir / "analysis" / "combat-ocr"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (output_dir / "replay-summary.json").write_text(
        json.dumps(replay_summary.to_dict(), indent=2),
        encoding="utf-8",
    )
    return summary


def parse_frame_index(frame_name: str) -> int:
    match = re.search(r"frame_(\d+)", frame_name)
    if match is None:
        return -1
    return int(match.group(1))


def frame_index_to_timestamp_ms(frame_index: int, replay_fps: int | float | None) -> int | None:
    if replay_fps is None or replay_fps <= 0 or frame_index < 0:
        return None
    return int(round((frame_index / replay_fps) * 1000))


def load_replay_metadata(session_dir: Path) -> dict[str, object]:
    metadata_path = session_dir / "metadata.json"
    if not metadata_path.exists():
        return {}

    data = json.loads(metadata_path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def score_ocr_result(
    raw_text: str,
    parsed_value: int | None,
    line_score: float,
    member_count: int,
    width: int,
    height: int,
) -> float:
    score = min(line_score / 12.0, 1.0) * 0.35

    if parsed_value is not None:
        score += 0.35
    if is_plausible_damage_text(raw_text):
        score += 0.2

    if raw_text and raw_text[0].isdigit():
        score += 0.1
    if any(char in raw_text for char in "kKmMbB"):
        score += 0.1
    if any(char in raw_text for char in ".,"):
        score += 0.05
    if 2 <= member_count <= 6:
        score += 0.05

    if parsed_value == 0:
        score -= 0.4
    if raw_text and not is_plausible_damage_text(raw_text):
        score -= 0.35
    if raw_text.startswith("0") and len(raw_text) > 1 and not raw_text.startswith("0."):
        score -= 0.25
    if raw_text and not any(char.isdigit() for char in raw_text):
        score -= 0.4
    if len(raw_text) <= 1:
        score -= 0.3
    if raw_text[-1:] in {"K", "M", "B"} and sum(char.isdigit() for char in raw_text) == 1 and width >= 50:
        score -= 0.2
    if parsed_value is not None and parsed_value < 1_000 and not any(char in raw_text for char in "kKmMbB"):
        score -= 0.25
    if width < 28 or height < 16:
        score -= 0.15

    return max(0.0, min(score, 1.0))


def dedupe_hits(
    results: list[dict[str, object]],
    frame_window: int = 3,
    center_distance_threshold: float = 70.0,
    min_confidence: float = 0.6,
    replay_fps: int | float | None = None,
) -> list[StableDamageHit]:
    stable_hits: list[StableDamageHit] = []

    sorted_results = sorted(
        (
            result
            for result in results
            if result["parsed_value"] is not None
            and result["confidence"] >= min_confidence
            and result.get("is_plausible", True)
        ),
        key=lambda item: (int(item["frame_index"]), -float(item["confidence"])),
    )

    for result in sorted_results:
        parsed_value = int(result["parsed_value"])
        frame_index = int(result["frame_index"])
        center_x = (int(result["left"]) + int(result["right"])) / 2
        center_y = (int(result["top"]) + int(result["bottom"])) / 2

        matched = False
        for hit in stable_hits:
            if not values_can_merge(hit.parsed_value, parsed_value):
                continue
            if frame_index - hit.last_frame > frame_window:
                continue
            if abs(center_x - hit.center_x) > center_distance_threshold:
                continue
            if abs(center_y - hit.center_y) > center_distance_threshold:
                continue

            hit.last_frame = frame_index
            hit.occurrences += 1
            if float(result["confidence"]) > hit.confidence:
                hit.confidence = float(result["confidence"])
                hit.parsed_value = parsed_value
                hit.sample_text = str(result["raw_text"])
                hit.center_x = center_x
                hit.center_y = center_y
            matched = True
            break

        if matched:
            continue

        stable_hits.append(
            StableDamageHit(
                frame_index=frame_index,
                timestamp_ms=frame_index_to_timestamp_ms(frame_index, replay_fps),
                parsed_value=parsed_value,
                confidence=float(result["confidence"]),
                sample_text=str(result["raw_text"]),
                center_x=center_x,
                center_y=center_y,
                first_frame=frame_index,
                last_frame=frame_index,
                occurrences=1,
            )
        )

    return sorted(
        stable_hits,
        key=lambda item: (-item.occurrences, -item.confidence, item.first_frame),
    )


def values_can_merge(first_value: int, second_value: int) -> bool:
    if first_value == second_value:
        return True

    larger_value = max(first_value, second_value)
    smaller_value = min(first_value, second_value)
    absolute_delta = larger_value - smaller_value

    if larger_value < 1_000:
        return absolute_delta <= 5

    relative_delta = absolute_delta / larger_value
    if larger_value >= 1_000_000:
        return relative_delta <= 0.03

    return relative_delta <= 0.015


def render_summary(summary: dict[str, object]) -> str:
    replay_summary = summary.get("replay_summary", {})
    lines = [
        f"Session: {replay_summary.get('session_name', 'unknown-session')}",
        f"Duration ms: {replay_summary.get('duration_ms', 0)}",
        f"Total damage: {replay_summary.get('total_damage', 0)}",
        f"Hit count: {replay_summary.get('hit_count', 0)}",
        f"Average hit: {replay_summary.get('average_hit', 0):.2f}",
        f"Biggest hit: {replay_summary.get('biggest_hit', 0)}",
        f"OCR candidates processed: {summary['candidate_count']}",
        f"Recognized non-empty text: {summary['recognized_count']}",
        f"Parsed numeric values: {summary['parsed_count']}",
        f"Confident OCR values: {summary['confident_count']}",
        f"Stable deduped hits: {summary['stable_hit_count']}",
        f"Repeated stable hits: {summary.get('repeated_hit_count', 0)}",
        f"Max occurrences in one hit: {summary.get('max_occurrences', 0)}",
        f"Seed lines expanded: {summary.get('seed_line_count', 0)}",
        "Top DPS buckets:",
    ]
    for bucket in replay_summary.get("dps_timeline", [])[:5]:
        lines.append(
            f"- {bucket['start_ms']}-{bucket['end_ms']} ms: damage={bucket['damage']} hits={bucket['hit_count']} dps={bucket['dps']:.2f}"
        )
    lines.extend(
        [
        "Top OCR results:",
        ]
    )
    for item in summary["results"][:10]:
        lines.append(
            f"- {item['mask_name']}: text='{item['raw_text']}' normalized='{item.get('normalized_text', item['raw_text'])}' parsed={item['parsed_value']} confidence={item['confidence']:.2f} plausible={item.get('is_plausible', True)}"
        )
    lines.append("Top stable hits:")
    for item in summary["stable_hits"][:10]:
        lines.append(
            f"- value={item['parsed_value']} frame={item.get('frame_index', item['first_frame'])} timestamp_ms={item.get('timestamp_ms')} frames={item['first_frame']}-{item['last_frame']} occurrences={item['occurrences']} confidence={item['best_confidence']:.2f} text='{item['sample_text']}'"
        )
    lines.append("Artifacts written to analysis/combat-ocr/ including replay-summary.json")
    return "\n".join(lines)


def main(session_path: str) -> int:
    summary = analyze_replay_ocr(Path(session_path))
    print(render_summary(summary))
    return 0
