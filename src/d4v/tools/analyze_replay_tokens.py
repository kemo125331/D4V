from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from PIL import Image, ImageOps

from d4v.tools.analyze_replay_roi import DEFAULT_DAMAGE_ROI, iter_frame_paths
from d4v.vision.color_mask import build_combat_text_mask
from d4v.vision.grouping import GroupedCandidate, group_bounding_boxes
from d4v.vision.roi import scale_relative_roi
from d4v.vision.segments import segment_damage_tokens


@dataclass(frozen=True)
class TokenCandidate:
    frame_name: str
    token_name: str
    mask_name: str
    pixel_count: int
    width: int
    height: int
    score: float
    is_ocr_ready: bool


@dataclass(frozen=True)
class LineCandidate:
    frame_name: str
    line_name: str
    mask_name: str
    left: int
    top: int
    right: int
    bottom: int
    pixel_count: int
    width: int
    height: int
    member_count: int
    score: float
    is_ocr_ready: bool


def select_frame_paths_for_segmentation(
    scored_frames: list[tuple[Path, int]],
    top_frame_count: int,
    neighbor_radius: int = 0,
) -> tuple[list[tuple[Path, int]], list[tuple[Path, int]]]:
    if not scored_frames:
        return [], []

    ranked_indices = sorted(
        range(len(scored_frames)),
        key=lambda index: scored_frames[index][1],
        reverse=True,
    )[:top_frame_count]
    seed_frames = [scored_frames[index] for index in ranked_indices]

    selected_indices: set[int] = set()
    for index in ranked_indices:
        start = max(0, index - neighbor_radius)
        stop = min(len(scored_frames), index + neighbor_radius + 1)
        selected_indices.update(range(start, stop))

    selected_frames = [scored_frames[index] for index in sorted(selected_indices)]
    return seed_frames, selected_frames


def recommend_top_frame_count(
    frame_count: int,
    min_frames: int = 6,
    max_frames: int = 30,
    coverage_ratio: float = 0.12,
) -> int:
    if frame_count <= 0:
        return min_frames
    recommended = max(min_frames, int(round(frame_count * coverage_ratio)))
    return min(recommended, max_frames)


def score_token_candidate(width: int, height: int, pixel_count: int) -> float:
    area = max(width * height, 1)
    fill_ratio = pixel_count / area
    aspect_ratio = width / max(height, 1)

    target_width = 46.0
    target_height = 28.0
    target_fill = 0.34
    target_aspect = 1.8

    width_score = max(0.0, 1.0 - abs(width - target_width) / target_width)
    height_score = max(0.0, 1.0 - abs(height - target_height) / target_height)
    fill_score = max(0.0, 1.0 - abs(fill_ratio - target_fill) / target_fill)
    aspect_score = max(0.0, 1.0 - abs(aspect_ratio - target_aspect) / target_aspect)

    score = (
        (width_score * 3.0)
        + (height_score * 3.0)
        + (fill_score * 2.0)
        + (aspect_score * 2.0)
    )

    if 24 <= width <= 90:
        score += 1.5
    if 14 <= height <= 56:
        score += 1.5
    if 80 <= pixel_count <= 1200:
        score += 1.0
    if aspect_ratio >= 1.35:
        score += 1.5

    if width > 90:
        score -= 2.0
    if height > 70:
        score -= 2.0
    if pixel_count > 1800:
        score -= 2.5
    if fill_ratio > 0.8:
        score -= 2.0
    if width < 24:
        score -= 2.5
    if aspect_ratio < 1.1:
        score -= 2.5

    return score


def is_ocr_ready_candidate(width: int, height: int, pixel_count: int) -> bool:
    score = score_token_candidate(width, height, pixel_count)
    return (
        score >= 7.0
        and 24 <= width <= 90
        and 14 <= height <= 70
        and 80 <= pixel_count <= 1800
        and width / max(height, 1) >= 1.1
    )


def score_line_candidate(width: int, height: int, pixel_count: int, member_count: int) -> float:
    area = max(width * height, 1)
    fill_ratio = pixel_count / area
    aspect_ratio = width / max(height, 1)

    score = 0.0
    if 24 <= width <= 260:
        score += 3.0
    if 12 <= height <= 150:
        score += 3.0
    if 1.5 <= aspect_ratio <= 5.0:
        score += 2.0
    if 2 <= member_count <= 6:
        score += 2.0
    if 0.15 <= fill_ratio <= 0.7:
        score += 2.0

    if member_count == 1:
        score -= 3.0
    if width > 280:
        score -= 2.5
    if height > 160:
        score -= 2.5
    if fill_ratio > 0.75:
        score -= 2.0

    return score


def is_ocr_ready_line(width: int, height: int, pixel_count: int, member_count: int) -> bool:
    return (
        score_line_candidate(width, height, pixel_count, member_count) >= 5.0
        and 16 <= width <= 260
        and 12 <= height <= 90
        and member_count >= 2
    )


def extract_replay_tokens(
    session_dir: Path,
    relative_roi: tuple[float, float, float, float] = DEFAULT_DAMAGE_ROI,
    top_frame_count: int | None = None,
    neighbor_radius: int = 0,
    recent_frame_limit: int | None = None,
) -> dict[str, object]:
    frame_paths = iter_frame_paths(session_dir)
    if recent_frame_limit is not None and recent_frame_limit > 0:
        frame_paths = frame_paths[-recent_frame_limit:]
    if not frame_paths:
        raise FileNotFoundError(f"No replay frames found in {session_dir}")

    with Image.open(frame_paths[0]) as first_frame:
        roi = scale_relative_roi(first_frame.size, relative_roi)

    scored_frames: list[tuple[Path, int]] = []
    for frame_path in frame_paths:
        with Image.open(frame_path) as image:
            crop = image.crop((roi.left, roi.top, roi.right, roi.bottom))
            scored_frames.append((frame_path, int(sum(build_combat_text_mask(crop).histogram()[-1:]))))

    if top_frame_count is None:
        top_frame_count = recommend_top_frame_count(len(frame_paths))

    seed_frames, selected_frames = select_frame_paths_for_segmentation(
        scored_frames,
        top_frame_count=top_frame_count,
        neighbor_radius=neighbor_radius,
    )

    output_dir = session_dir / "analysis" / "combat-tokens"
    output_dir.mkdir(parents=True, exist_ok=True)
    candidates: list[TokenCandidate] = []
    line_output_dir = session_dir / "analysis" / "combat-lines"
    line_output_dir.mkdir(parents=True, exist_ok=True)
    line_candidates: list[LineCandidate] = []

    for frame_path, _score in selected_frames:
        with Image.open(frame_path) as image:
            crop = image.crop((roi.left, roi.top, roi.right, roi.bottom)).convert("RGB")
            mask = build_combat_text_mask(crop)
            components = segment_damage_tokens(mask)

            frame_dir = output_dir / Path(frame_path.name).stem
            frame_dir.mkdir(parents=True, exist_ok=True)

            for index, component in enumerate(components):
                token_name = f"token_{index:03d}.png"
                mask_name = f"token_{index:03d}_mask.png"
                token = crop.crop(
                    (
                        component.left,
                        component.top,
                        component.right + 1,
                        component.bottom + 1,
                    )
                )
                token_mask = mask.crop(
                    (
                        component.left,
                        component.top,
                        component.right + 1,
                        component.bottom + 1,
                    )
                )
                ImageOps.expand(token, border=4, fill=(0, 0, 0)).save(frame_dir / token_name)
                ImageOps.expand(token_mask.convert("L"), border=4, fill=0).save(frame_dir / mask_name)
                score = score_token_candidate(component.width, component.height, component.pixel_count)
                candidates.append(
                    TokenCandidate(
                        frame_name=frame_path.name,
                        token_name=f"{Path(frame_path.name).stem}/{token_name}",
                        mask_name=f"{Path(frame_path.name).stem}/{mask_name}",
                        pixel_count=component.pixel_count,
                        width=component.width,
                        height=component.height,
                        score=score,
                        is_ocr_ready=is_ocr_ready_candidate(
                            component.width,
                            component.height,
                            component.pixel_count,
                        ),
                    )
                )

            grouped_candidates = group_bounding_boxes(components)
            line_frame_dir = line_output_dir / Path(frame_path.name).stem
            line_frame_dir.mkdir(parents=True, exist_ok=True)

            for index, grouped in enumerate(grouped_candidates):
                line_name = f"line_{index:03d}.png"
                mask_name = f"line_{index:03d}_mask.png"
                line_image = crop.crop(
                    (
                        grouped.left,
                        grouped.top,
                        grouped.right + 1,
                        grouped.bottom + 1,
                    )
                )
                line_mask = mask.crop(
                    (
                        grouped.left,
                        grouped.top,
                        grouped.right + 1,
                        grouped.bottom + 1,
                    )
                )
                ImageOps.expand(line_image, border=4, fill=(0, 0, 0)).save(line_frame_dir / line_name)
                ImageOps.expand(line_mask.convert("L"), border=4, fill=0).save(line_frame_dir / mask_name)
                line_score = score_line_candidate(
                    grouped.width,
                    grouped.height,
                    grouped.pixel_count,
                    grouped.member_count,
                )
                line_candidates.append(
                    LineCandidate(
                        frame_name=frame_path.name,
                        line_name=f"{Path(frame_path.name).stem}/{line_name}",
                        mask_name=f"{Path(frame_path.name).stem}/{mask_name}",
                        left=grouped.left,
                        top=grouped.top,
                        right=grouped.right,
                        bottom=grouped.bottom,
                        pixel_count=grouped.pixel_count,
                        width=grouped.width,
                        height=grouped.height,
                        member_count=grouped.member_count,
                        score=line_score,
                        is_ocr_ready=is_ocr_ready_line(
                            grouped.width,
                            grouped.height,
                            grouped.pixel_count,
                            grouped.member_count,
                        ),
                    )
                )

    ranked_candidates = sorted(candidates, key=lambda item: (item.is_ocr_ready, item.score, item.pixel_count), reverse=True)
    ranked_lines = sorted(
        line_candidates,
        key=lambda item: (item.is_ocr_ready, item.score, item.pixel_count),
        reverse=True,
    )
    summary = {
        "session_dir": str(session_dir),
        "frame_count": len(frame_paths),
        "recent_frame_limit": recent_frame_limit,
        "top_frame_count": len(seed_frames),
        "selected_frame_count": len(selected_frames),
        "neighbor_radius": neighbor_radius,
        "token_count": len(candidates),
        "ocr_ready_token_count": sum(1 for candidate in candidates if candidate.is_ocr_ready),
        "line_count": len(line_candidates),
        "ocr_ready_line_count": sum(1 for candidate in line_candidates if candidate.is_ocr_ready),
        "top_frames": [
            {
                "frame_name": frame_path.name,
                "yellow_pixel_count": score,
            }
            for frame_path, score in seed_frames
        ],
        "tokens": [
            {
                "frame_name": candidate.frame_name,
                "token_name": candidate.token_name,
                "mask_name": candidate.mask_name,
                "pixel_count": candidate.pixel_count,
                "width": candidate.width,
                "height": candidate.height,
                "score": candidate.score,
                "is_ocr_ready": candidate.is_ocr_ready,
            }
            for candidate in ranked_candidates
        ],
        "lines": [
            {
                "frame_name": candidate.frame_name,
                "line_name": candidate.line_name,
                "mask_name": candidate.mask_name,
                "left": candidate.left,
                "top": candidate.top,
                "right": candidate.right,
                "bottom": candidate.bottom,
                "pixel_count": candidate.pixel_count,
                "width": candidate.width,
                "height": candidate.height,
                "member_count": candidate.member_count,
                "score": candidate.score,
                "is_ocr_ready": candidate.is_ocr_ready,
            }
            for candidate in ranked_lines
        ],
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def render_summary(summary: dict[str, object]) -> str:
    lines = summary["lines"]
    lines = [
        f"Replay frame count: {summary['frame_count']}",
        f"Recent frame limit: {summary.get('recent_frame_limit')}",
        f"Seed frames selected: {summary['top_frame_count']}",
        f"Frames segmented with neighbors: {summary['selected_frame_count']}",
        f"Token candidates exported: {summary['token_count']}",
        f"OCR-ready candidates: {summary['ocr_ready_token_count']}",
        f"Line candidates exported: {summary['line_count']}",
        f"OCR-ready line candidates: {summary['ocr_ready_line_count']}",
        "Top ranked line exports:",
    ]
    for item in summary["lines"][:8]:
        lines.append(
            f"- {item['line_name']}: {item['width']}x{item['height']} px ({item['pixel_count']} pixels, members={item['member_count']}, score={item['score']:.1f}, ocr_ready={item['is_ocr_ready']})"
        )
    lines.append("Artifacts written to analysis/combat-tokens/ and analysis/combat-lines/")
    return "\n".join(lines)


def main(session_path: str) -> int:
    summary = extract_replay_tokens(Path(session_path))
    print(render_summary(summary))
    return 0
