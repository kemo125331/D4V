from PIL import Image


def count_combat_text_pixels(image: Image.Image) -> int:
    histogram = build_combat_text_mask(image).histogram()
    return histogram[255]


def build_combat_text_mask(image: Image.Image) -> Image.Image:
    rgb = image.convert("RGB")
    mask = Image.new("L", rgb.size, color=0)
    width, height = rgb.size
    rgb_pixels = rgb.load()
    mask_pixels = mask.load()

    for y in range(height):
        for x in range(width):
            r, g, b = rgb_pixels[x, y]
            
            is_white = r >= 190 and g >= 190 and b >= 190
            is_yellow_or_orange = r >= 160 and g >= 100 and b <= 140 and r >= g
            is_blue = r <= 150 and g >= 160 and b >= 180
            
            if is_white or is_yellow_or_orange or is_blue:
                mask_pixels[x, y] = 255

    return mask
