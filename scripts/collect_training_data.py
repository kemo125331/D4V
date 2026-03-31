#!/usr/bin/env python3
"""Data collection tool for ML training.

Captures screenshots during gameplay and saves them with OCR labels
for training a custom model on your specific setup.

Usage:
    python scripts/collect_training_data.py

Then press:
    - SPACE: Capture current screen
    - ESC: Stop collecting
    - R: Toggle recording mode (auto-capture every 5 seconds)
"""

import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from PIL import Image, ImageGrab
from d4v.vision.pipeline import CombatTextPipeline
from d4v.vision.config import VisionConfig


class DataCollector:
    """Collects training data from live gameplay."""

    def __init__(self, output_dir: Path | None = None):
        self.output_dir = output_dir or Path("fixtures/training_data_collected")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.pipeline = CombatTextPipeline()
        self.collected_samples: List[dict] = []
        self.running = True

        print("=" * 60)
        print("D4V Training Data Collector")
        print("=" * 60)
        print(f"\nSaving to: {self.output_dir.absolute()}")
        print("\nControls:")
        print("  SPACE - Capture screenshot now")
        print("  R     - Toggle auto-capture (every 5 seconds)")
        print("  ESC   - Stop collecting")
        print("=" * 60)

    def capture_screen(self) -> Image.Image | None:
        """Capture current screen."""
        try:
            screenshot = ImageGrab.grab()
            return screenshot
        except Exception as e:
            print(f"Capture error: {e}")
            return None

    def process_frame(self, image: Image.Image, frame_num: int) -> List[dict]:
        """Process frame and extract training samples."""
        timestamp = datetime.now()
        filename = f"frame_{frame_num:06d}_{timestamp.strftime('%Y%m%d_%H%M%S')}"

        # Run detection
        hits = self.pipeline.process_image(image, frame_num, int(time.time() * 1000))

        samples = []
        for hit in hits:
            sample = {
                "frame": frame_num,
                "timestamp": timestamp.isoformat(),
                "value": hit.parsed_value,
                "confidence": hit.confidence,
                "text": hit.sample_text,
                "center_x": hit.center_x,
                "center_y": hit.center_y,
                "filename": filename,
            }
            samples.append(sample)
            self.collected_samples.append(sample)

        # Save screenshot
        image.save(self.output_dir / f"{filename}.png")

        # Save metadata
        if samples:
            import json

            with open(self.output_dir / f"{filename}.json", "w") as f:
                json.dump(samples, f, indent=2)

        return samples

    def run_interactive(self):
        """Run interactive collection mode."""
        print("\nStarting interactive mode...")
        print("Press Ctrl+C to stop\n")

        frame_num = 0
        auto_capture = False
        last_capture = 0

        try:
            while self.running:
                # Check for auto-capture
                if auto_capture and (time.time() - last_capture) > 5:
                    print(f"\n[Auto-capture {frame_num}]")
                    screenshot = self.capture_screen()
                    if screenshot:
                        samples = self.process_frame(screenshot, frame_num)
                        if samples:
                            print(f"  ✓ Detected {len(samples)} hits:")
                            for s in samples[:3]:
                                print(f"    - {s['value']:,} ({s['confidence']:.0%})")
                            if len(samples) > 3:
                                print(f"    ... and {len(samples) - 3} more")
                        else:
                            print("  - No hits detected")
                    frame_num += 1
                    last_capture = time.time()

                time.sleep(0.1)

        except KeyboardInterrupt:
            print("\n\nStopping collection...")

        self.save_summary()

    def save_summary(self):
        """Save collection summary."""
        import json

        summary = {
            "total_samples": len(self.collected_samples),
            "total_frames": len(set(s["frame"] for s in self.collected_samples)),
            "samples": self.collected_samples,
            "collected_at": datetime.now().isoformat(),
        }

        with open(self.output_dir / "collection_summary.json", "w") as f:
            json.dump(summary, f, indent=2)

        print("\n" + "=" * 60)
        print("Collection Summary")
        print("=" * 60)
        print(f"Total samples: {len(self.collected_samples)}")
        print(f"Total frames: {summary['total_frames']}")
        print(f"Saved to: {self.output_dir.absolute()}")
        print("\nNext step: Run training script")
        print("  python scripts/train_custom_model.py")
        print("=" * 60)


def main():
    collector = DataCollector()
    collector.run_interactive()


if __name__ == "__main__":
    main()
