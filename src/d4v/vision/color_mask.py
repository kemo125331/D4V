from __future__ import annotations

import cv2
import numpy as np
from PIL import Image


def count_combat_text_pixels(image: Image.Image) -> int:
    return int(np.count_nonzero(np.array(build_combat_text_mask(image))))


def build_combat_text_mask(image: Image.Image) -> Image.Image:
    """
    Return a binary PIL "L" mask where combat-text pixels are 255.

    Colour ranges (in HSV — OpenCV uses H: 0-180, S: 0-255, V: 0-255):
      - Yellow/orange damage numbers  hue  10–30,  S ≥ 120, V ≥ 140
      - White text                         S ≤ 40,  V ≥ 190
      - Blue text (freeze/cold)       hue  90–130, S ≥ 100, V ≥ 140
      - Red/crimson crits             hue  0–8  and 172–180, S ≥ 130, V ≥ 130
      - Green (shields, life drain)   hue  40–85,  S ≥ 100, V ≥ 100
      - Purple/magenta (poison/shadow) hue 130–165, S ≥ 100, V ≥ 100
    """
    rgb = image.convert("RGB")
    bgr = cv2.cvtColor(np.array(rgb), cv2.COLOR_RGB2BGR)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

    yellow_orange = cv2.inRange(hsv, (10, 120, 140), (30, 255, 255))
    white         = cv2.inRange(hsv, (0, 0, 190),    (180, 40, 255))
    blue          = cv2.inRange(hsv, (90, 100, 140),  (130, 255, 255))
    red_low       = cv2.inRange(hsv, (0, 130, 130),   (8, 255, 255))
    red_high      = cv2.inRange(hsv, (172, 130, 130), (180, 255, 255))
    green         = cv2.inRange(hsv, (40, 100, 100),  (85, 255, 255))
    purple        = cv2.inRange(hsv, (130, 100, 100), (165, 255, 255))

    combined = cv2.bitwise_or(yellow_orange, white)
    combined = cv2.bitwise_or(combined, blue)
    combined = cv2.bitwise_or(combined, red_low)
    combined = cv2.bitwise_or(combined, red_high)
    combined = cv2.bitwise_or(combined, green)
    combined = cv2.bitwise_or(combined, purple)

    return Image.fromarray(combined, mode="L")
