"""Synthetic frame generator for testing without game captures.

Generates synthetic damage numbers for testing the detection pipeline
when real game captures are not available.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from PIL import Image, ImageDraw, ImageFont


@dataclass
class DamageNumber:
    """Represents a synthetic damage number.

    Attributes:
        value: Damage value to display.
        x: X position (center).
        y: Y position (center).
        font_size: Font size in pixels.
        damage_type: Type of damage (direct, crit, dot, etc.).
        suffix: Value suffix (K, M, B) or empty.
    """

    value: int
    x: int
    y: int
    font_size: int = 24
    damage_type: str = "direct"
    suffix: str = ""

    @property
    def display_text(self) -> str:
        """Get display text with suffix."""
        if self.suffix:
            return f"{self.value}{self.suffix}"
        return str(self.value)

    @property
    def color(self) -> str:
        """Get damage number color based on type."""
        colors = {
            "direct": "#FFA500",  # Orange
            "crit": "#FFD700",  # Gold (brighter)
            "dot": "#00FF00",  # Green
            "cold": "#0080FF",  # Blue
            "fire": "#FF4500",  # Red-orange
            "lightning": "#9932CC",  # Purple
            "white": "#FFFFFF",  # White
        }
        return colors.get(self.damage_type, "#FFA500")


@dataclass
class FrameConfig:
    """Configuration for a synthetic frame.

    Attributes:
        width: Frame width in pixels.
        height: Frame height in pixels.
        background: Background color or "black", "game", "gradient".
        damage_numbers: List of damage numbers to render.
        noise_level: Amount of visual noise (0-100).
        blur_amount: Gaussian blur amount (0 = none).
    """

    width: int = 1920
    height: int = 1080
    background: Literal["black", "game", "gradient"] = "black"
    damage_numbers: list[DamageNumber] | None = None
    noise_level: int = 0
    blur_amount: int = 0

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.damage_numbers is None:
            self.damage_numbers = []
        if not 0 <= self.noise_level <= 100:
            raise ValueError("noise_level must be between 0 and 100")
        if self.blur_amount < 0:
            raise ValueError("blur_amount must be non-negative")


class SyntheticFrameGenerator:
    """Generates synthetic frames with damage numbers for testing.

    Example:
        generator = SyntheticFrameGenerator(seed=42)

        # Generate single frame
        config = FrameConfig(
            width=1920,
            height=1080,
            damage_numbers=[
                DamageNumber(value=1234, x=500, y=300, damage_type="crit"),
                DamageNumber(value=5678, x=700, y=400, damage_type="direct"),
            ],
        )
        image = generator.generate_frame(config)
        image.save("test_frame.png")

        # Generate frame sequence
        frames = generator.generate_sequence(
            num_frames=100,
            output_dir=Path("fixtures/replays/synthetic_001/frames"),
        )
    """

    def __init__(self, seed: int | None = None) -> None:
        """Initialize generator.

        Args:
            seed: Random seed for reproducibility.
        """
        self.rng = random.Random(seed)

    def generate_frame(self, config: FrameConfig) -> Image.Image:
        """Generate a single synthetic frame.

        Args:
            config: Frame configuration.

        Returns:
            PIL Image with rendered damage numbers.
        """
        # Create base image
        image = self._create_background(config)
        draw = ImageDraw.Draw(image)

        # Try to load a font, fall back to default
        try:
            font = ImageFont.truetype("arial.ttf", 24)
        except OSError:
            font = ImageFont.load_default()

        # Draw damage numbers
        for damage in config.damage_numbers:
            self._draw_damage_number(draw, damage, font)

        # Add noise if configured
        if config.noise_level > 0:
            image = self._add_noise(image, config.noise_level)

        # Apply blur if configured
        if config.blur_amount > 0:
            from PIL import ImageFilter
            image = image.filter(ImageFilter.GaussianBlur(config.blur_amount))

        return image

    def _create_background(self, config: FrameConfig) -> Image.Image:
        """Create frame background.

        Args:
            config: Frame configuration.

        Returns:
            PIL Image with background.
        """
        if config.background == "black":
            return Image.new("RGB", (config.width, config.height), (0, 0, 0))

        elif config.background == "gradient":
            # Create vertical gradient (dark to slightly lighter)
            image = Image.new("RGB", (config.width, config.height))
            for y in range(config.height):
                brightness = int(20 + (y / config.height) * 30)
                color = (brightness, brightness, brightness + 10)
                draw = ImageDraw.Draw(image)
                draw.line((0, y, config.width, y), fill=color)
            return image

        elif config.background == "game":
            # Simulate game-like background with some variation
            image = Image.new("RGB", (config.width, config.height))
            for y in range(config.height):
                # Dark brownish-gray gradient
                base = int(30 + (y / config.height) * 20)
                r = base + 10
                g = base
                b = base - 5
                draw = ImageDraw.Draw(image)
                draw.line((0, y, config.width, y), fill=(r, g, b))
            return image

        else:
            return Image.new("RGB", (config.width, config.height), (0, 0, 0))

    def _draw_damage_number(
        self,
        draw: ImageDraw.ImageDraw,
        damage: DamageNumber,
        font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    ) -> None:
        """Draw a damage number on the image.

        Args:
            draw: PIL ImageDraw object.
            damage: Damage number to draw.
            font: Font to use.
        """
        text = damage.display_text

        # Get text bounding box
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # Center the text
        x = damage.x - text_width // 2
        y = damage.y - text_height // 2

        # Draw text with shadow for visibility
        shadow_offset = 2
        draw.text(
            (x + shadow_offset, y + shadow_offset),
            text,
            font=font,
            fill="#000000",
        )
        draw.text(
            (x, y),
            text,
            font=font,
            fill=damage.color,
        )

    def _add_noise(self, image: Image.Image, level: int) -> Image.Image:
        """Add visual noise to image.

        Args:
            image: Input image.
            level: Noise level (0-100).

        Returns:
            Image with noise added.
        """
        import numpy as np

        # Convert to numpy array
        arr = np.array(image)

        # Generate noise using numpy (not random.gauss which doesn't support size)
        noise_scale = level / 100.0 * 50  # Max 50 intensity
        noise = np.random.normal(0, noise_scale, size=arr.shape)

        # Add noise and clip to valid range
        arr = np.clip(arr + noise, 0, 255).astype(np.uint8)

        return Image.fromarray(arr)

    def generate_sequence(
        self,
        num_frames: int,
        output_dir: Path | str,
        config: FrameConfig | None = None,
        fps: float = 30.0,
        damage_pattern: str = "combat",
    ) -> list[Path]:
        """Generate a sequence of frames simulating combat.

        Args:
            num_frames: Number of frames to generate.
            output_dir: Directory to save frames.
            config: Base frame configuration.
            fps: Frames per second (for timing).
            damage_pattern: Pattern type ("combat", "burst", "dot", "mixed").

        Returns:
            List of saved frame paths.
        """
        config = config or FrameConfig()
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        saved_paths: list[Path] = []

        # Track active damage numbers (they float upward and fade)
        active_damage: list[DamageNumber] = []

        for frame_idx in range(num_frames):
            # Spawn new damage based on pattern
            new_damage = self._spawn_damage(
                frame_idx=frame_idx,
                pattern=damage_pattern,
                config=config,
            )
            active_damage.extend(new_damage)

            # Update existing damage (float upward)
            for damage in active_damage:
                damage.y -= 2  # Move up 2 pixels per frame

            # Remove off-screen damage
            active_damage = [d for d in active_damage if d.y > -50]

            # Create frame config
            frame_config = FrameConfig(
                width=config.width,
                height=config.height,
                background=config.background,
                damage_numbers=active_damage.copy(),
                noise_level=config.noise_level,
                blur_amount=config.blur_amount,
            )

            # Generate and save
            image = self.generate_frame(frame_config)
            output_path = output_dir / f"frame_{frame_idx:06d}.png"
            image.save(output_path)
            saved_paths.append(output_path)

        return saved_paths

    def _spawn_damage(
        self,
        frame_idx: int,
        pattern: str,
        config: FrameConfig,
    ) -> list[DamageNumber]:
        """Spawn new damage numbers based on pattern.

        Args:
            frame_idx: Current frame index.
            pattern: Damage pattern type.
            config: Frame configuration.

        Returns:
            List of new damage numbers.
        """
        new_damage: list[DamageNumber] = []

        if pattern == "combat":
            # Steady stream of damage
            if frame_idx % 5 == 0:  # Every 5 frames
                new_damage.append(self._random_damage(config))

        elif pattern == "burst":
            # Bursts of damage
            if frame_idx % 30 == 0:
                for _ in range(5):  # 5 damage numbers at once
                    new_damage.append(self._random_damage(config))

        elif pattern == "dot":
            # Rapid small ticks
            if frame_idx % 3 == 0:
                new_damage.append(DamageNumber(
                    value=self.rng.randint(50, 200),
                    x=self.rng.randint(400, 800),
                    y=self.rng.randint(300, 500),
                    font_size=18,
                    damage_type="dot",
                ))

        elif pattern == "mixed":
            # Mix of all patterns
            if frame_idx % 10 == 0:
                new_damage.append(self._random_damage(config))
            if frame_idx % 30 == 0:
                for _ in range(3):
                    new_damage.append(self._random_damage(config))
            if frame_idx % 50 == 0:
                # Big crit
                new_damage.append(DamageNumber(
                    value=self.rng.randint(50000, 200000),
                    x=self.rng.randint(400, 800),
                    y=self.rng.randint(300, 500),
                    font_size=36,
                    damage_type="crit",
                    suffix="K" if self.rng.random() > 0.5 else "",
                ))

        return new_damage

    def _random_damage(self, config: FrameConfig) -> DamageNumber:
        """Generate a random damage number.

        Args:
            config: Frame configuration.

        Returns:
            Random damage number.
        """
        # Damage value distribution
        roll = self.rng.random()
        if roll < 0.6:
            value = self.rng.randint(100, 5000)
            suffix = ""
        elif roll < 0.85:
            value = self.rng.randint(10, 99)
            suffix = "K"
        elif roll < 0.95:
            value = self.rng.randint(100, 999)
            suffix = "K"
        else:
            value = self.rng.randint(1, 9)
            suffix = "M"

        # Damage type distribution
        type_roll = self.rng.random()
        if type_roll < 0.6:
            damage_type = "direct"
        elif type_roll < 0.8:
            damage_type = "crit"
        elif type_roll < 0.9:
            damage_type = "dot"
        else:
            damage_type = self.rng.choice(["cold", "fire", "lightning"])

        return DamageNumber(
            value=value,
            suffix=suffix,
            x=self.rng.randint(int(config.width * 0.15), int(config.width * 0.85)),
            y=self.rng.randint(int(config.height * 0.1), int(config.height * 0.7)),
            font_size=self.rng.randint(20, 32) if damage_type == "crit" else 24,
            damage_type=damage_type,
        )


def generate_test_fixtures(
    output_dir: Path | str | None = None,
    seed: int = 42,
) -> dict[str, list[Path]]:
    """Generate standard test fixture suite.

    Creates multiple synthetic replay scenarios for testing.

    Args:
        output_dir: Base output directory. Defaults to fixtures/replays/.
        seed: Random seed for reproducibility.

    Returns:
        Dictionary mapping scenario name to list of frame paths.
    """
    output_dir = Path(output_dir) if output_dir else Path(__file__).parent.parent.parent / "fixtures" / "replays"
    output_dir.mkdir(parents=True, exist_ok=True)

    generator = SyntheticFrameGenerator(seed=seed)
    results: dict[str, list[Path]] = {}

    # Scenario 1: Normal combat
    print("Generating: normal_combat")
    results["normal_combat"] = generator.generate_sequence(
        num_frames=200,
        output_dir=output_dir / "synthetic_normal_combat" / "frames",
        config=FrameConfig(background="game"),
        damage_pattern="combat",
    )

    # Scenario 2: Burst damage
    print("Generating: burst_damage")
    results["burst_damage"] = generator.generate_sequence(
        num_frames=150,
        output_dir=output_dir / "synthetic_burst_damage" / "frames",
        config=FrameConfig(background="gradient"),
        damage_pattern="burst",
    )

    # Scenario 3: DoT ticks
    print("Generating: dot_ticks")
    results["dot_ticks"] = generator.generate_sequence(
        num_frames=100,
        output_dir=output_dir / "synthetic_dot_ticks" / "frames",
        config=FrameConfig(background="black", noise_level=10),
        damage_pattern="dot",
    )

    # Scenario 4: Mixed combat
    print("Generating: mixed_combat")
    results["mixed_combat"] = generator.generate_sequence(
        num_frames=300,
        output_dir=output_dir / "synthetic_mixed_combat" / "frames",
        config=FrameConfig(background="game", noise_level=5),
        damage_pattern="mixed",
    )

    # Scenario 5: High crit rate
    print("Generating: high_crits")
    crit_rng = random.Random(123)
    crit_config = FrameConfig(background="game")
    crit_config.damage_numbers = [
        DamageNumber(
            value=crit_rng.randint(10000, 50000),
            x=crit_rng.randint(400, 800),
            y=crit_rng.randint(300, 500),
            font_size=32,
            damage_type="crit",
        )
        for _ in range(3)
    ]
    results["high_crits"] = generator.generate_sequence(
        num_frames=100,
        output_dir=output_dir / "synthetic_high_crits" / "frames",
        config=crit_config,
        damage_pattern="burst",
    )

    print(f"\nGenerated {len(results)} synthetic scenarios in {output_dir}")
    for name, paths in results.items():
        print(f"  {name}: {len(paths)} frames")

    return results


if __name__ == "__main__":
    # Generate test fixtures when run directly
    generate_test_fixtures()
