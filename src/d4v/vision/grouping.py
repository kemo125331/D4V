from dataclasses import dataclass

from d4v.vision.segments import BoundingBox


@dataclass(frozen=True)
class GroupedCandidate:
    members: tuple[BoundingBox, ...]
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

    @property
    def member_count(self) -> int:
        return len(self.members)

    @property
    def center_y(self) -> float:
        return (self.top + self.bottom) / 2

    @property
    def average_member_width(self) -> float:
        return sum(member.width for member in self.members) / self.member_count

    @property
    def average_member_height(self) -> float:
        return sum(member.height for member in self.members) / self.member_count


def group_bounding_boxes(
    boxes: list[BoundingBox],
    max_group_width: int = 260,
    max_group_height: int = 90,
    max_group_members: int = 15,
) -> list[GroupedCandidate]:
    groups: list[GroupedCandidate] = []

    for box in sorted(boxes, key=lambda item: (item.top, item.left)):
        best_group_index: int | None = None
        best_gap: float | None = None

        for index, group in enumerate(groups):
            if not should_merge_box_into_group(
                box,
                group,
                max_group_width=max_group_width,
                max_group_height=max_group_height,
                max_group_members=max_group_members,
            ):
                continue

            gap = horizontal_gap(box, group)
            if best_gap is None or gap < best_gap:
                best_gap = gap
                best_group_index = index

        if best_group_index is None:
            groups.append(group_from_boxes((box,)))
            continue

        chosen_group = groups[best_group_index]
        groups[best_group_index] = group_from_boxes((*chosen_group.members, box))

    return sorted(groups, key=lambda item: (item.top, item.left))


def group_from_boxes(boxes: tuple[BoundingBox, ...]) -> GroupedCandidate:
    return GroupedCandidate(
        members=tuple(sorted(boxes, key=lambda item: (item.left, item.top))),
        left=min(box.left for box in boxes),
        top=min(box.top for box in boxes),
        right=max(box.right for box in boxes),
        bottom=max(box.bottom for box in boxes),
        pixel_count=sum(box.pixel_count for box in boxes),
    )


def should_merge_box_into_group(
    box: BoundingBox,
    group: GroupedCandidate,
    max_group_width: int,
    max_group_height: int,
    max_group_members: int,
) -> bool:
    if group.member_count >= max_group_members:
        return False

    if box.left < group.left - 6:
        return False

    gap = horizontal_gap(box, group)
    if gap > max(int(group.average_member_width * 3.0), 15):
        if not allow_punctuation_merge(box, group) and not allow_suffix_merge(box, group):
            return False

    overlap = vertical_overlap_ratio(box, group)
    center_distance = abs(box_center_y(box) - group.center_y)
    if overlap < 0.15 and center_distance > max(group.average_member_height, box.height) * 0.7:
        if not allow_punctuation_merge(box, group):
            return False

    merged_left = min(group.left, box.left)
    merged_top = min(group.top, box.top)
    merged_right = max(group.right, box.right)
    merged_bottom = max(group.bottom, box.bottom)
    merged_width = merged_right - merged_left + 1
    merged_height = merged_bottom - merged_top + 1

    return merged_width <= max_group_width and merged_height <= max_group_height


def horizontal_gap(box: BoundingBox, group: GroupedCandidate) -> int:
    if box.left > group.right:
        return box.left - group.right - 1
    if box.right < group.left:
        return group.left - box.right - 1
    return 0


def vertical_overlap_ratio(box: BoundingBox, group: GroupedCandidate) -> float:
    overlap_top = max(box.top, group.top)
    overlap_bottom = min(box.bottom, group.bottom)
    if overlap_bottom < overlap_top:
        return 0.0
    overlap_height = overlap_bottom - overlap_top + 1
    return overlap_height / max(min(box.height, group.height), 1)


def box_center_y(box: BoundingBox) -> float:
    return (box.top + box.bottom) / 2


def allow_punctuation_merge(box: BoundingBox, group: GroupedCandidate) -> bool:
    if box.width > 40 or box.height > 60:
        return False
    if box.height > group.average_member_height * 0.8:
        return False
    if horizontal_gap(box, group) > 30:
        return False
    return box_center_y(box) >= group.top + (group.height / 2)


def allow_suffix_merge(box: BoundingBox, group: GroupedCandidate) -> bool:
    if box.width > 100 or box.height > 120:
        return False
    if horizontal_gap(box, group) > 40:
        return False
    return abs(box_center_y(box) - group.center_y) <= max(group.average_member_height, box.height) * 0.4
