from __future__ import annotations

import cv2
import numpy as np
from PIL import Image


def count_combat_text_pixels(image: Image.Image) -> int:
    return int(np.count_nonzero(np.array(build_combat_text_mask(image))))


def build_combat_text_mask(image: Image.Image) -> Image.Image:
    """
    Return a binary PIL "L" mask where combat-text pixels are 255.

    Colour ranges (in HSV):
      - Yellow/orange damage numbers  hue  10–30, S ≥ 120, V ≥ 140
      - White text                    S ≤ 40,      V ≥ 190
      - Blue text (freeze/cold)       hue  90–130, S ≥ 100, V ≥ 140
    """
    rgb = image.convert("RGB")
    bgr = cv2.cvtColor(np.array(rgb), cv2.COLOR_RGB2BGR)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

    yellow_orange = cv2.inRange(hsv, (10, 120, 140), (30, 255, 255))
    white = cv2.inRange(hsv, (0, 0, 190), (180, 40, 255))
    blue = cv2.inRange(hsv, (90, 100, 140), (130, 255, 255))

    combined = cv2.bitwise_or(yellow_orange, white)
    combined = cv2.bitwise_or(combined, blue)

    return Image.fromarray(combined, mode="L")
