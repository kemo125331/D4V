from PIL import Image

from d4v.vision.segments import find_connected_components, segment_damage_tokens


def test_find_connected_components_returns_separate_boxes():
    mask = Image.new("L", (12, 12), color=0)
    for x in range(1, 4):
        for y in range(1, 8):
            mask.putpixel((x, y), 255)
    for x in range(7, 10):
        for y in range(2, 10):
            mask.putpixel((x, y), 255)

    boxes = find_connected_components(mask, min_pixels=5, min_width=2, min_height=4)

    assert len(boxes) == 2
    assert boxes[0].left == 1
    assert boxes[0].top == 1
    assert boxes[1].left == 7
    assert boxes[1].top == 2


def test_segment_damage_tokens_splits_wide_component_on_vertical_gap():
    mask = Image.new("L", (18, 12), color=0)
    for x in range(1, 7):
        for y in range(2, 10):
            mask.putpixel((x, y), 255)
    for x in range(10, 16):
        for y in range(2, 10):
            mask.putpixel((x, y), 255)
    for x in range(7, 10):
        mask.putpixel((x, 6), 255)

    boxes = segment_damage_tokens(mask, min_pixels=5, min_width=2, min_height=4, max_merge_width_ratio=1.0)

    assert len(boxes) == 2
    assert boxes[0].left == 1
    assert boxes[1].left == 10
