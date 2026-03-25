from dataclasses import dataclass

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
    binary = mask.convert("L")
    width, height = binary.size
    pixels = binary.load()
    visited = bytearray(width * height)
    components: list[BoundingBox] = []

    def idx(x: int, y: int) -> int:
        return (y * width) + x

    for y in range(height):
        for x in range(width):
            flat_index = idx(x, y)
            if visited[flat_index] or pixels[x, y] == 0:
                continue

            stack = [(x, y)]
            visited[flat_index] = 1
            left = right = x
            top = bottom = y
            pixel_count = 0

            while stack:
                current_x, current_y = stack.pop()
                pixel_count += 1
                left = min(left, current_x)
                right = max(right, current_x)
                top = min(top, current_y)
                bottom = max(bottom, current_y)

                for next_x, next_y in (
                    (current_x - 1, current_y),
                    (current_x + 1, current_y),
                    (current_x, current_y - 1),
                    (current_x, current_y + 1),
                ):
                    if next_x < 0 or next_y < 0 or next_x >= width or next_y >= height:
                        continue
                    next_index = idx(next_x, next_y)
                    if visited[next_index] or pixels[next_x, next_y] == 0:
                        continue
                    visited[next_index] = 1
                    stack.append((next_x, next_y))

            box = BoundingBox(
                left=left,
                top=top,
                right=right,
                bottom=bottom,
                pixel_count=pixel_count,
            )
            if box.pixel_count < min_pixels or box.width < min_width or box.height < min_height:
                continue
            components.append(box)

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
