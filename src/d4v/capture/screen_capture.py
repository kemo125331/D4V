from PIL import Image
import mss

from d4v.capture.game_window import get_diablo_iv_bounds, is_diablo_iv_foreground


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
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        shot = sct.grab(monitor)
        return Image.frombytes("RGB", shot.size, shot.rgb)


def capture_game_window_image(require_foreground: bool = False) -> Image.Image | None:
    if require_foreground and not is_diablo_iv_foreground():
        return None

    bounds = get_diablo_iv_bounds()
    if bounds is None:
        return None

    with mss.mss() as sct:
        monitor = {
            "left": bounds.left,
            "top": bounds.top,
            "width": bounds.width,
            "height": bounds.height,
        }
        shot = sct.grab(monitor)
        return Image.frombytes("RGB", shot.size, shot.rgb)
