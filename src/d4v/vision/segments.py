from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image


@dataclass(frozen=True)
class BoundingBox:
    left: int
    top: int
    right: int
    bottom: int
    pixel_count: int

    @property
    def width(self) -> int:
        return self.right - self.left + 1

    @property
    def height(self) -> int:
        return self.bottom - self.top + 1


def find_connected_components(
    mask: Image.Image,
    min_pixels: int = 20,
    min_width: int = 4,
    min_height: int = 6,
) -> list[BoundingBox]:
    """
    Find connected blobs in a binary PIL mask using cv2.connectedComponentsWithStats.

    Returns the same list[BoundingBox] contract as the previous BFS implementation.
    """
    binary = np.array(mask.convert("L"))
    # OpenCV CCA requires uint8 binary image (0 or 255).
    _, thresh = cv2.threshold(binary, 0, 255, cv2.THRESH_BINARY)

    num_labels, _, stats, _ = cv2.connectedComponentsWithStats(thresh, connectivity=4)

    components: list[BoundingBox] = []
    # Label 0 is the background; start from 1.
    for label in range(1, num_labels):
        x = int(stats[label, cv2.CC_STAT_LEFT])
        y = int(stats[label, cv2.CC_STAT_TOP])
        w = int(stats[label, cv2.CC_STAT_WIDTH])
        h = int(stats[label, cv2.CC_STAT_HEIGHT])
        area = int(stats[label, cv2.CC_STAT_AREA])

        if area < min_pixels or w < min_width or h < min_height:
            continue

        components.append(
            BoundingBox(
                left=x,
                top=y,
                right=x + w - 1,
                bottom=y + h - 1,
                pixel_count=area,
            )
        )

    return sorted(components, key=lambda box: (box.top, box.left))


def segment_damage_tokens(
    mask: Image.Image,
    min_pixels: int = 20,
    min_width: int = 4,
    min_height: int = 6,
    max_merge_width_ratio: float = 1.6,
) -> list[BoundingBox]:
    components = find_connected_components(
        mask,
        min_pixels=min_pixels,
        min_width=min_width,
        min_height=min_height,
    )
    refined: list[BoundingBox] = []
    for component in components:
        if component.width <= int(component.height * max_merge_width_ratio):
            refined.append(component)
            continue
        splits = split_component_by_vertical_gaps(
            mask,
            component,
            min_pixels=min_pixels,
            min_width=min_width,
            min_height=min_height,
        )
        refined.extend(splits or [component])
    return sorted(refined, key=lambda box: (box.top, box.left))


def split_component_by_vertical_gaps(
    mask: Image.Image,
    component: BoundingBox,
    min_pixels: int,
    min_width: int,
    min_height: int,
) -> list[BoundingBox]:
    """Column-scan split on sub-region — kept as pure Python (runs on small crops)."""
    binary = mask.convert("L")
    pixels = binary.load()
    column_counts: list[int] = []

    for x in range(component.left, component.right + 1):
        count = 0
        for y in range(component.top, component.bottom + 1):
            if pixels[x, y] > 0:
                count += 1
        column_counts.append(count)

    segments: list[tuple[int, int]] = []
    start: int | None = None
    for offset, count in enumerate(column_counts):
        if count > 1 and start is None:
            start = offset
        elif count <= 1 and start is not None:
            segments.append((start, offset - 1))
            start = None
    if start is not None:
        segments.append((start, len(column_counts) - 1))

    if len(segments) <= 1:
        return []

    split_boxes: list[BoundingBox] = []
    for start_offset, end_offset in segments:
        left = component.left + start_offset
        right = component.left + end_offset
        top = None
        bottom = None
        pixel_count = 0

        for x in range(left, right + 1):
            for y in range(component.top, component.bottom + 1):
                if pixels[x, y] == 0:
                    continue
                pixel_count += 1
                top = y if top is None else min(top, y)
                bottom = y if bottom is None else max(bottom, y)

        if top is None or bottom is None:
            continue

        box = BoundingBox(
            left=left,
            top=top,
            right=right,
            bottom=bottom,
            pixel_count=pixel_count,
        )
        if box.pixel_count < min_pixels or box.width < min_width or box.height < min_height:
            continue
        split_boxes.append(box)

    return split_boxes
