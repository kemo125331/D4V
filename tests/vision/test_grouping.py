from d4v.vision.grouping import group_bounding_boxes
from d4v.vision.segments import BoundingBox


def test_group_bounding_boxes_merges_adjacent_same_baseline_boxes():
    boxes = [
        BoundingBox(left=10, top=10, right=18, bottom=30, pixel_count=120),
        BoundingBox(left=22, top=11, right=32, bottom=30, pixel_count=130),
        BoundingBox(left=35, top=12, right=44, bottom=31, pixel_count=110),
    ]

    groups = group_bounding_boxes(boxes)

    assert len(groups) == 1
    assert groups[0].member_count == 3
    assert groups[0].left == 10
    assert groups[0].right == 44


def test_group_bounding_boxes_keeps_separate_rows_apart():
    boxes = [
        BoundingBox(left=10, top=10, right=18, bottom=28, pixel_count=120),
        BoundingBox(left=22, top=10, right=31, bottom=28, pixel_count=120),
        BoundingBox(left=12, top=45, right=20, bottom=63, pixel_count=120),
    ]

    groups = group_bounding_boxes(boxes)

    assert len(groups) == 2
    assert groups[0].member_count == 2
    assert groups[1].member_count == 1
