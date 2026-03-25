from dataclasses import dataclass
import ctypes
from ctypes import wintypes


@dataclass(frozen=True)
class GameWindowBounds:
    left: int
    top: int
    width: int
    height: int


def get_diablo_iv_bounds() -> GameWindowBounds | None:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except AttributeError:
        pass

    hwnd = ctypes.windll.user32.FindWindowW(None, "Diablo IV")
    if not hwnd:
        return None

    rect = wintypes.RECT()
    if not ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(rect)):
        return None

    pt = wintypes.POINT(0, 0)
    if not ctypes.windll.user32.ClientToScreen(hwnd, ctypes.byref(pt)):
        return None

    width = rect.right - rect.left
    height = rect.bottom - rect.top

    if width <= 0 or height <= 0:
        return None

    return GameWindowBounds(
        left=pt.x,
        top=pt.y,
        width=width,
        height=height,
    )
