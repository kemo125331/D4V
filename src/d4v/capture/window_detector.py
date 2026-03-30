"""Cross-platform window detection abstraction.

Provides unified window detection API for Windows, Linux, and macOS.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class GameWindowBounds:
    """Game window bounds.

    Attributes:
        left: Left coordinate.
        top: Top coordinate.
        right: Right coordinate.
        bottom: Bottom coordinate.
        width: Window width.
        height: Window height.
    """

    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        """Get window width."""
        return self.right - self.left

    @property
    def height(self) -> int:
        """Get window height."""
        return self.bottom - self.top

    def to_tuple(self) -> tuple[int, int, int, int]:
        """Convert to (left, top, right, bottom) tuple."""
        return (self.left, self.top, self.right, self.bottom)

    def to_dict(self) -> dict[str, int]:
        """Convert to dictionary."""
        return {
            "left": self.left,
            "top": self.top,
            "right": self.right,
            "bottom": self.bottom,
            "width": self.width,
            "height": self.height,
        }


class WindowDetector(Protocol):
    """Protocol for platform-specific window detection."""

    def find_game_window(self, title_pattern: str = "Diablo") -> GameWindowBounds | None:
        """Find game window by title pattern.

        Args:
            title_pattern: Window title pattern to match.

        Returns:
            GameWindowBounds or None.
        """
        ...


class WindowsWindowDetector:
    """Windows-specific window detection using Win32 API."""

    def find_game_window(
        self,
        title_pattern: str = "Diablo",
    ) -> GameWindowBounds | None:
        """Find Diablo IV window on Windows.

        Args:
            title_pattern: Window title pattern.

        Returns:
            GameWindowBounds or None.
        """
        try:
            import ctypes
            from ctypes import wintypes

            # Define callback type
            WNDENUMPROC = ctypes.WINFUNCTYPE(
                wintypes.BOOL,
                wintypes.HWND,
                wintypes.LPARAM,
            )

            # Store found window
            found_hwnd = None
            found_title = None

            def enum_callback(hwnd: int, lParam: int) -> bool:
                nonlocal found_hwnd, found_title

                # Get window title
                title_length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                if title_length == 0:
                    return True

                buffer = ctypes.create_unicode_buffer(title_length + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buffer, title_length + 1)

                title = buffer.value
                if title_pattern.lower() in title.lower():
                    found_hwnd = hwnd
                    found_title = title
                    return False  # Stop enumeration

                return True

            # Enumerate windows
            callback = WNDENUMPROC(enum_callback)
            ctypes.windll.user32.EnumWindows(callback, 0)

            if found_hwnd is None:
                return None

            # Get window rect
            rect = ctypes.wintypes.RECT()
            ctypes.windll.user32.GetWindowRect(found_hwnd, ctypes.byref(rect))

            return GameWindowBounds(
                left=rect.left,
                top=rect.top,
                right=rect.right,
                bottom=rect.bottom,
            )

        except (ImportError, OSError):
            return None


class LinuxWindowDetector:
    """Linux window detection using X11 or Wayland."""

    def find_game_window(
        self,
        title_pattern: str = "Diablo",
    ) -> GameWindowBounds | None:
        """Find Diablo IV window on Linux.

        Args:
            title_pattern: Window title pattern.

        Returns:
            GameWindowBounds or None.
        """
        # Try X11 first
        bounds = self._find_x11_window(title_pattern)
        if bounds:
            return bounds

        # Try Wayland
        bounds = self._find_wayland_window(title_pattern)
        return bounds

    def _find_x11_window(
        self,
        title_pattern: str,
    ) -> GameWindowBounds | None:
        """Find window using X11.

        Args:
            title_pattern: Window title pattern.

        Returns:
            GameWindowBounds or None.
        """
        try:
            from Xlib import X, display

            disp = display.Display()
            root = disp.screen().root

            # Get all windows
            windows = root.query_tree().children

            for window in windows:
                wm_name = window.get_wm_name()
                if wm_name and title_pattern.lower() in wm_name.lower():
                    geometry = window.get_geometry()
                    coords = window.translate_coords(root, 0, 0)

                    return GameWindowBounds(
                        left=coords.x,
                        top=coords.y,
                        right=coords.x + geometry.width,
                        bottom=coords.y + geometry.height,
                    )

        except (ImportError, Exception):
            pass

        return None

    def _find_wayland_window(
        self,
        title_pattern: str,
    ) -> GameWindowBounds | None:
        """Find window using Wayland (limited support).

        Args:
            title_pattern: Window title pattern.

        Returns:
            GameWindowBounds or None.
        """
        # Wayland doesn't allow direct window enumeration
        # Fall back to screen capture of entire screen
        try:
            from PIL import ImageGrab
            bbox = ImageGrab.grab().size
            return GameWindowBounds(
                left=0,
                top=0,
                right=bbox[0],
                bottom=bbox[1],
            )
        except Exception:
            pass

        return None


class MacOsWindowDetector:
    """macOS window detection using Quartz/Accessibility API."""

    def find_game_window(
        self,
        title_pattern: str = "Diablo",
    ) -> GameWindowBounds | None:
        """Find Diablo IV window on macOS.

        Args:
            title_pattern: Window title pattern.

        Returns:
            GameWindowBounds or None.
        """
        try:
            import Quartz

            # Get all windows
            window_list = Quartz.CGWindowListCopyWindowInfo(
                Quartz.kCGWindowListOptionOnScreenOnly,
                Quartz.kCGNullWindowID,
            )

            if window_list is None:
                return None

            for window in window_list:
                title = window.get(Quartz.kCGWindowName, "")
                owner = window.get(Quartz.kCGWindowOwnerName, "")

                if title_pattern.lower() in str(title).lower() or \
                   title_pattern.lower() in str(owner).lower():
                    bounds = window.get(Quartz.kCGWindowBounds, {})
                    if bounds:
                        return GameWindowBounds(
                            left=int(bounds.get("X", 0)),
                            top=int(bounds.get("Y", 0)),
                            right=int(bounds.get("X", 0) + bounds.get("Width", 0)),
                            bottom=int(bounds.get("Y", 0) + bounds.get("Height", 0)),
                        )

        except (ImportError, Exception):
            pass

        return None


def get_window_detector() -> WindowDetector:
    """Get platform-appropriate window detector.

    Returns:
        WindowDetector instance for current platform.
    """
    if sys.platform == "win32":
        return WindowsWindowDetector()
    elif sys.platform == "linux":
        return LinuxWindowDetector()
    elif sys.platform == "darwin":
        return MacOsWindowDetector()
    else:
        # Unknown platform - return dummy detector
        class DummyDetector:
            def find_game_window(self, title_pattern: str = "Diablo") -> None:
                return None

        return DummyDetector()  # type: ignore


def find_game_window(title_pattern: str = "Diablo") -> GameWindowBounds | None:
    """Find game window on current platform.

    Args:
        title_pattern: Window title pattern to match.

    Returns:
        GameWindowBounds or None.
    """
    detector = get_window_detector()
    return detector.find_game_window(title_pattern)
