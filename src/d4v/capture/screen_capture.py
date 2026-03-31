from __future__ import annotations

from PIL import Image
import mss
import mss.tools

from d4v.capture.game_window import get_diablo_iv_bounds, is_diablo_iv_foreground

# ---------------------------------------------------------------------------
# Persistent mss context — creating mss.mss() on every call costs ~20ms.
# We keep a single module-level instance that is reused across all grabs.
# ---------------------------------------------------------------------------
_sct: mss.base.MSSBase | None = None


def _get_sct() -> mss.base.MSSBase:
    global _sct
    if _sct is None:
        _sct = mss.mss()
    return _sct


def normalize_roi(
    roi: tuple[int, int, int, int],
    window_size: tuple[int, int],
) -> tuple[int, int, int, int]:
    x, y, width, height = roi
    max_width, max_height = window_size
    return (
        x,
        y,
        max(0, min(width, max_width - x)),
        max(0, min(height, max_height - y)),
    )


def capture_primary_monitor_image() -> Image.Image:
    sct = _get_sct()
    monitor = sct.monitors[1]
    shot = sct.grab(monitor)
    return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")


# Relative damage ROI — must match VisionConfig.damage_roi
# (0.15, 0.05, 0.70, 0.75) → left=15%, top=5%, width=70%, height=75%
_ROI_LEFT = 0.10  # grab a little wider than the vision ROI for safety
_ROI_TOP = 0.02
_ROI_WIDTH = 0.80
_ROI_HEIGHT = 0.82


def capture_game_window_image(require_foreground: bool = True) -> Image.Image | None:
    """Capture the Diablo IV game window ROI.

    Args:
        require_foreground: If True, only capture when D4 is the active window.
            This prevents reading desktop/other window content when D4 is
            minimized or behind other windows.

    Returns:
        PIL Image of the game window ROI, or None if capture failed.
    """
    if require_foreground and not is_diablo_iv_foreground():
        return None

    bounds = get_diablo_iv_bounds()
    if bounds is None:
        return None

    # Grab only the ROI sub-region of the game window.
    # This is the area where floating damage numbers appear (top 80% of screen).
    # At 2560×1440: ~2048×1180 instead of 2560×1440 → ~40% fewer pixels → ~40% faster grab.
    left = bounds.left + int(bounds.width * _ROI_LEFT)
    top = bounds.top + int(bounds.height * _ROI_TOP)
    width = int(bounds.width * _ROI_WIDTH)
    height = int(bounds.height * _ROI_HEIGHT)

    monitor = {"left": left, "top": top, "width": width, "height": height}
    sct = _get_sct()
    shot = sct.grab(monitor)
    # BGRX raw decode is faster than .rgb (avoids an extra full-frame copy)
    return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
