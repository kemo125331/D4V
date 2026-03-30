#!/usr/bin/env python3
"""Debug tool to check what the vision pipeline is detecting."""

import os
import sys
from pathlib import Path

# Set Tesseract path BEFORE importing anything else
os.environ["TESSERACT_CMD"] = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from PIL import ImageGrab
from d4v.vision.pipeline import CombatTextPipeline
from d4v.vision.color_mask import build_combat_text_mask

print("=" * 60)
print("D4V Vision Pipeline Debug")
print("=" * 60)

# Capture screen
print("\n1. Capturing screen...")
try:
    screenshot = ImageGrab.grab()
    print(f"   ✓ Captured: {screenshot.width}x{screenshot.height}")
except Exception as e:
    print(f"   ✗ Failed: {e}")
    sys.exit(1)

# Create pipeline
print("\n2. Loading pipeline...")
pipeline = CombatTextPipeline()
print(f"   ✓ ML threshold: {pipeline.confidence_classifier.threshold}")
print(f"   ✓ Min confidence: {pipeline.config.min_confidence}")

# Process image
print("\n3. Processing frame...")
try:
    hits = pipeline.process_image(screenshot, frame_index=0, timestamp_ms=0)
    print(f"   ✓ Detected {len(hits)} hits")
    
    if hits:
        print("\n4. Detected Damage:")
        for hit in hits:
            print(f"   - {hit.parsed_value:,} ({hit.confidence:.2%}) - {hit.sample_text}")
    else:
        print("\n4. ⚠ NO DAMAGE DETECTED")
        print("\n   Possible causes:")
        print("   a) No Diablo IV window visible")
        print("   b) ROI in wrong position")
        print("   c) Color mask not matching")
        print("   d) OCR not reading text")
        
        # Check color mask
        print("\n5. Checking color mask...")
        mask = build_combat_text_mask(screenshot)
        mask_pixels = sum(1 for p in mask.getdata() if p > 0)
        total_pixels = mask.width * mask.height
        mask_ratio = mask_pixels / total_pixels if total_pixels > 0 else 0
        
        print(f"   Mask pixels: {mask_pixels:,} of {total_pixels:,} ({mask_ratio:.2%})")
        
        if mask_ratio < 0.001:
            print("   ⚠ Very few combat text pixels detected!")
            print("   → Check if Diablo IV is visible and combat is happening")
        elif mask_ratio > 0.1:
            print("   ⚠ Too many pixels! Might be capturing UI")
        else:
            print("   ✓ Mask looks reasonable")
        
except Exception as e:
    print(f"   ✗ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
