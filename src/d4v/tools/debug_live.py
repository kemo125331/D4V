"""
Quick live diagnostic: captures one frame from the Diablo IV window and
dumps every OCR candidate, raw text, normalized text, parsed value,
plausibility and confidence. Run while Diablo IV is open.

Usage:
    uv run python -m d4v.tools.debug_live
"""
from __future__ import annotations

from PIL import ImageOps

from d4v.capture.screen_capture import capture_game_window_image
from d4v.tools.analyze_replay_roi import DEFAULT_DAMAGE_ROI
from d4v.tools.analyze_replay_tokens import is_ocr_ready_line, score_line_candidate
from d4v.tools.analyze_replay_ocr import score_ocr_result
from d4v.vision.classifier import (
    is_plausible_damage_text,
    normalize_damage_text,
    parse_damage_value,
)
from d4v.vision.color_mask import build_combat_text_mask
from d4v.vision.grouping import group_bounding_boxes
from d4v.vision.ocr import ocr_pil_image
from d4v.vision.roi import scale_relative_roi
from d4v.vision.segments import segment_damage_tokens


def main() -> None:
    import time

    print("Capturing 5 frames over 2 seconds — attack the dummy now!")
    best_image = None
    best_pixels = -1

    for i in range(5):
        image = capture_game_window_image()
        if image is None:
            print(f"  Frame {i+1}: ERROR — Diablo IV window not found")
            continue
        roi = scale_relative_roi(image.size, DEFAULT_DAMAGE_ROI)
        crop = image.crop((roi.left, roi.top, roi.right, roi.bottom)).convert("RGB")
        mask = build_combat_text_mask(crop)
        pixels = sum(mask.histogram()[-1:])
        print(f"  Frame {i+1}/5: {pixels} combat pixels")
        if pixels > best_pixels:
            best_pixels = pixels
            best_image = image
        if i < 4:
            time.sleep(0.4)

    if best_image is None:
        print("ERROR: Could not capture any frame.")
        return

    print(f"\nUsing best frame with {best_pixels} combat pixels")
    image = best_image
    roi = scale_relative_roi(image.size, DEFAULT_DAMAGE_ROI)
    print(f"  Frame size: {image.size}")
    print(f"  ROI: left={roi.left} top={roi.top} right={roi.right} bottom={roi.bottom}")
    crop = image.crop((roi.left, roi.top, roi.right, roi.bottom)).convert("RGB")

    mask = build_combat_text_mask(crop)
    components = segment_damage_tokens(mask)
    groups = group_bounding_boxes(components)

    print(f"  Segmented components: {len(components)}")
    print(f"  Grouped candidates: {len(groups)}")

    print()
    print(f"{'#':>3}  {'W':>5}{'H':>5}{'px':>7}{'mem':>5}  {'ocr_rdy':>8}  {'score':>7}  {'raw_text':>16}  {'norm':>14}  {'parsed':>16}  {'plausible':>10}  {'conf':>6}")
    print("-" * 120)

    for idx, grp in enumerate(
        sorted(groups, key=lambda g: score_line_candidate(g.width, g.height, g.pixel_count, g.member_count), reverse=True)[:24]
    ):
        ocr_ready = is_ocr_ready_line(grp.width, grp.height, grp.pixel_count, grp.member_count)
        line_score = score_line_candidate(grp.width, grp.height, grp.pixel_count, grp.member_count)

        line_mask = mask.crop((grp.left, grp.top, grp.right + 1, grp.bottom + 1))
        expanded = ImageOps.expand(line_mask.convert("L"), border=4, fill=0)
        raw_text = ocr_pil_image(expanded)
        norm = normalize_damage_text(raw_text) if raw_text else ""
        parsed = parse_damage_value(norm) if norm else None
        plausible = is_plausible_damage_text(norm) if norm else False
        conf = score_ocr_result(
            raw_text=norm,
            parsed_value=parsed,
            line_score=line_score,
            member_count=grp.member_count,
            width=grp.width,
            height=grp.height,
        )

        print(
            f"{idx:>3}  {grp.width:>5}{grp.height:>5}{grp.pixel_count:>7}{grp.member_count:>5}  "
            f"{'YES' if ocr_ready else 'no':>8}  {line_score:>7.2f}  "
            f"{repr(raw_text)[:16]:>16}  {repr(norm)[:14]:>14}  "
            f"{str(parsed):>16}  {'YES' if plausible else 'no':>10}  {conf:>6.2f}"
        )

    print()
    print("Done.")


if __name__ == "__main__":
    main()
