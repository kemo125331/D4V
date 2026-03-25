from PIL import Image

from d4v.vision.color_mask import build_combat_text_mask, count_combat_text_pixels


def test_count_combat_text_pixels_counts_damage_like_pixels():
    image = Image.new("RGB", (2, 2), color=(0, 0, 0))
    image.putpixel((0, 0), (230, 200, 80))
    image.putpixel((1, 0), (120, 120, 120))
    assert count_combat_text_pixels(image) == 1


def test_build_combat_text_mask_marks_damage_like_pixels():
    image = Image.new("RGB", (1, 2), color=(0, 0, 0))
    image.putpixel((0, 0), (230, 200, 80))
    mask = build_combat_text_mask(image)
    assert mask.getpixel((0, 0)) == 255
    assert mask.getpixel((0, 1)) == 0
