"""Generate synthetic test images simulating Diablo IV damage numbers.

Creates PNG fixtures with known damage values for OCR benchmarking.
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import random
import sys


def _get_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Get a font, falling back to default if needed."""
    paths = [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except IOError, OSError:
            continue
    return ImageFont.load_default()


def make_damage_image(
    text: str,
    fg_color: tuple[int, int, int] = (255, 200, 50),
    bg_color: tuple[int, int, int] = (30, 30, 45),
    font_size: int = 48,
    noise: bool = True,
    angle: float = 0.0,
) -> Image.Image:
    """Create a synthetic damage number image.

    Args:
        text: The damage text to render (e.g. "45.6M", "248K").
        fg_color: Foreground (text) color — D4 damage is yellow/orange.
        bg_color: Background color — dark like D4 combat area.
        font_size: Font size in pixels.
        noise: Add visual noise to simulate game rendering.
        angle: Slight rotation to simulate floating damage numbers.

    Returns:
        PIL Image with the damage number rendered.
    """
    font = _get_font(font_size)

    # Measure text size
    dummy = Image.new("RGB", (1, 1))
    d = ImageDraw.Draw(dummy)
    bbox = d.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    # Add padding
    pad = 20
    w, h = tw + pad * 2, th + pad * 2

    img = Image.new("RGB", (w, h), bg_color)
    draw = ImageDraw.Draw(img)

    # Draw text with slight glow
    if noise:
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                if dx == 0 and dy == 0:
                    continue
                draw.text((pad + dx, pad + dy), text, fill=(80, 60, 20), font=font)

    draw.text((pad, pad), text, fill=fg_color, font=font)

    # Add subtle noise pixels
    if noise:
        pixels = img.load()
        for _ in range(int(w * h * 0.002)):
            x, y = random.randint(0, w - 1), random.randint(0, h - 1)
            r, g, b = pixels[x, y]
            noise_val = random.randint(-15, 15)
            pixels[x, y] = (
                max(0, min(255, r + noise_val)),
                max(0, min(255, g + noise_val)),
                max(0, min(255, b + noise_val)),
            )

    if angle:
        img = img.rotate(angle, resample=Image.BICUBIC, expand=True)

    return img


def generate_fixtures(output_dir: str = "fixtures/replays/synthetic") -> list[Path]:
    """Generate a set of synthetic damage number fixtures.

    Returns:
        List of generated file paths.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Known damage values — these are typical D4 numbers
    samples = [
        ("45.6M", (255, 200, 50)),  # Yellow — normal damage
        ("248K", (255, 180, 40)),  # Orange — critical
        ("1.2B", (200, 100, 255)),  # Purple — vulnerable
        ("987", (255, 255, 255)),  # White — small
        ("3.14M", (255, 200, 50)),  # Yellow with decimal
        ("12,345", (255, 180, 40)),  # Comma-separated
        ("-500", (100, 255, 100)),  # Green — healing
        ("7.89B", (200, 100, 255)),  # Large purple
        ("156K", (255, 180, 40)),  # Medium orange
        ("0.5M", (255, 200, 50)),  # Small yellow
    ]

    paths = []
    for i, (text, color) in enumerate(samples):
        # Clean version
        img = make_damage_image(text, fg_color=color, noise=False)
        fname = (
            out / f"damage_{i:02d}_{text.replace('.', 'p').replace(',', 'c')}_clean.png"
        )
        img.save(fname)
        paths.append(fname)

        # Noisy version (more realistic)
        img_noisy = make_damage_image(
            text, fg_color=color, noise=True, angle=random.uniform(-5, 5)
        )
        fname_noisy = (
            out / f"damage_{i:02d}_{text.replace('.', 'p').replace(',', 'c')}_noisy.png"
        )
        img_noisy.save(fname_noisy)
        paths.append(fname_noisy)

    # Also create a full-frame-like image with multiple damage numbers
    full = Image.new("RGB", (1280, 720), (25, 25, 35))
    draw = ImageDraw.Draw(full)
    font = _get_font(36)
    positions = [
        (200, 150, "45.6M", (255, 200, 50)),
        (600, 300, "248K", (255, 180, 40)),
        (900, 200, "1.2B", (200, 100, 255)),
        (400, 500, "987", (255, 255, 255)),
        (750, 450, "3.14M", (255, 200, 50)),
    ]
    for x, y, text, color in positions:
        draw.text((x, y), text, fill=color, font=font)

    full_path = out / "full_frame_multi_damage.png"
    full.save(full_path)
    paths.append(full_path)

    print(f"Generated {len(paths)} synthetic fixtures in {out}")
    return paths


if __name__ == "__main__":
    generate_fixtures()
