from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from PIL import Image, ImageDraw

from d4v.vision.color_mask import build_combat_text_mask, count_combat_text_pixels
from d4v.vision.roi import Roi, scale_relative_roi

DEFAULT_DAMAGE_ROI = (0.15, 0.05, 0.70, 0.75)


@dataclass(frozen=True)
class FrameScore:
    frame_name: str
    yellow_pixel_count: int


def iter_frame_paths(session_dir: Path) -> list[Path]:
    return sorted(session_dir.glob("frame_*.png"))


def analyze_session_roi(
    session_dir: Path,
    relative_roi: tuple[float, float, float, float] = DEFAULT_DAMAGE_ROI,
) -> dict[str, object]:
    frame_paths = iter_frame_paths(session_dir)
    if not frame_paths:
        raise FileNotFoundError(f"No replay frames found in {session_dir}")

    with Image.open(frame_paths[0]) as first_frame:
        roi = scale_relative_roi(first_frame.size, relative_roi)

    output_dir = session_dir / "analysis" / "combat-roi"
    output_dir.mkdir(parents=True, exist_ok=True)

    scores: list[FrameScore] = []
    sample_exports: list[str] = []

    for frame_path in frame_paths:
        with Image.open(frame_path) as image:
            crop = image.crop((roi.left, roi.top, roi.right, roi.bottom))
            yellow_pixel_count = count_combat_text_pixels(crop)
            scores.append(
                FrameScore(
                    frame_name=frame_path.name,
                    yellow_pixel_count=yellow_pixel_count,
                )
            )

    top_frames = sorted(scores, key=lambda item: item.yellow_pixel_count, reverse=True)[:12]

    for score in top_frames:
        frame_path = session_dir / score.frame_name
        with Image.open(frame_path) as image:
            crop = image.crop((roi.left, roi.top, roi.right, roi.bottom))
            crop_output = output_dir / score.frame_name
            crop.save(crop_output)
            mask = build_combat_text_mask(crop)
            mask.save(output_dir / f"{Path(score.frame_name).stem}_mask.png")
            sample_exports.append(str(crop_output.name))

    create_contact_sheet(session_dir, roi, top_frames, output_dir / "contact-sheet.png")
    preview_frame_name = top_frames[0].frame_name if top_frames else frame_paths[0].name
    create_roi_preview(session_dir / preview_frame_name, roi, output_dir / "roi-preview.png")

    summary = {
        "session_dir": str(session_dir),
        "frame_count": len(frame_paths),
        "roi": {
            "left": roi.left,
            "top": roi.top,
            "width": roi.width,
            "height": roi.height,
        },
        "top_frames": [
            {
                "frame_name": score.frame_name,
                "yellow_pixel_count": score.yellow_pixel_count,
            }
            for score in top_frames
        ],
        "exported_crops": sample_exports,
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def create_roi_preview(frame_path: Path, roi: Roi, output_path: Path) -> None:
    with Image.open(frame_path) as image:
        preview = image.convert("RGB").copy()
        draw = ImageDraw.Draw(preview)
        draw.rectangle((roi.left, roi.top, roi.right, roi.bottom), outline=(255, 0, 0), width=4)
        preview.save(output_path)


def create_contact_sheet(
    session_dir: Path,
    roi: Roi,
    top_frames: list[FrameScore],
    output_path: Path,
) -> None:
    if not top_frames:
        return

    crops: list[tuple[Image.Image, str]] = []
    try:
        for score in top_frames:
            with Image.open(session_dir / score.frame_name) as image:
                crop = image.crop((roi.left, roi.top, roi.right, roi.bottom)).convert("RGB")
                crops.append((crop.copy(), f"{score.frame_name} ({score.yellow_pixel_count})"))

        columns = 3
        rows = (len(crops) + columns - 1) // columns
        thumb_width, thumb_height = crops[0][0].size
        label_height = 24

        sheet = Image.new(
            "RGB",
            (columns * thumb_width, rows * (thumb_height + label_height)),
            color=(20, 20, 20),
        )
        draw = ImageDraw.Draw(sheet)

        for index, (crop, label) in enumerate(crops):
            col = index % columns
            row = index // columns
            x = col * thumb_width
            y = row * (thumb_height + label_height)
            sheet.paste(crop, (x, y))
            draw.text((x + 8, y + thumb_height + 4), label, fill=(255, 255, 255))

        sheet.save(output_path)
    finally:
        for crop, _label in crops:
            crop.close()


def render_summary(summary: dict[str, object]) -> str:
    roi = summary["roi"]
    top_frames = summary["top_frames"]
    lines = [
        f"Replay frame count: {summary['frame_count']}",
        (
            "ROI: "
            f"left={roi['left']} top={roi['top']} width={roi['width']} height={roi['height']}"
        ),
        "Top ROI frames by yellow-text density:",
    ]
    for item in top_frames[:5]:
        lines.append(f"- {item['frame_name']}: {item['yellow_pixel_count']}")
    lines.append("Artifacts written to analysis/combat-roi/")
    return "\n".join(lines)


def main(session_path: str) -> int:
    summary = analyze_session_roi(Path(session_path))
    print(render_summary(summary))
    return 0
