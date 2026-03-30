"""Visual debug overlay for troubleshooting.

Renders detection results, ROIs, bounding boxes, and confidence
scores on frames for visual debugging.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Literal

from PIL import Image, ImageDraw, ImageFont


class DebugLayer(StrEnum):
    """Debug overlay layers."""

    ROI = "roi"
    BOUNDING_BOXES = "bounding_boxes"
    CONFIDENCE_SCORES = "confidence_scores"
    TEXT_LABELS = "text_labels"
    MOTION_VECTORS = "motion_vectors"
    HEATMAP = "heatmap"


@dataclass
class DebugConfig:
    """Configuration for debug overlay.

    Attributes:
        enabled_layers: Layers to render.
        roi_color: Color for ROI borders.
        box_color_fn: Function to get box color by confidence.
        show_confidence: Show confidence scores.
        show_text: Show OCR text.
        font_size: Font size for labels.
        line_width: Line width for borders.
    """

    enabled_layers: list[DebugLayer] | None = None
    roi_color: tuple[int, int, int] = (0, 255, 0)
    box_color_fn: callable | None = None
    show_confidence: bool = True
    show_text: bool = True
    font_size: int = 16
    line_width: int = 2

    def __post_init__(self) -> None:
        """Initialize config."""
        if self.enabled_layers is None:
            self.enabled_layers = list(DebugLayer)

        if self.box_color_fn is None:
            self.box_color_fn = self._default_box_color

    def _default_box_color(self, confidence: float) -> tuple[int, int, int]:
        """Get box color based on confidence.

        Args:
            confidence: Confidence score.

        Returns:
            RGB color tuple.
        """
        if confidence >= 0.8:
            return (0, 255, 0)  # Green
        elif confidence >= 0.6:
            return (255, 255, 0)  # Yellow
        else:
            return (255, 0, 0)  # Red


@dataclass
class DebugOverlay:
    """Debug overlay renderer.

    Example:
        overlay = DebugOverlay(
            config=DebugConfig(
                show_confidence=True,
                show_text=True,
            )
        )

        # Render on frame
        debug_image = overlay.render(
            frame=image,
            roi=(100, 50, 800, 600),
            detections=[...],
        )

        debug_image.save("debug_frame.png")
    """

    config: DebugConfig | None = None

    def __post_init__(self) -> None:
        """Initialize overlay."""
        self.config = self.config or DebugConfig()

    def render(
        self,
        frame: Image.Image,
        roi: tuple[int, int, int, int] | None = None,
        detections: list[dict[str, Any]] | None = None,
        motion_vectors: list[tuple[float, float, float, float]] | None = None,
        heatmap: Image.Image | None = None,
    ) -> Image.Image:
        """Render debug overlay on frame.

        Args:
            frame: Base frame image.
            roi: ROI tuple (left, top, right, bottom).
            detections: List of detection dictionaries.
            motion_vectors: List of motion vectors.
            heatmap: Optional heatmap overlay.

        Returns:
            Frame with debug overlay.
        """
        # Convert to RGB if needed
        result = frame.convert("RGB")
        draw = ImageDraw.Draw(result)

        # Load font
        try:
            font = ImageFont.truetype("arial.ttf", self.config.font_size)
        except OSError:
            font = ImageFont.load_default()

        # Render layers
        if DebugLayer.ROI in self.config.enabled_layers and roi:
            self._render_roi(draw, roi)

        if DebugLayer.BOUNDING_BOXES in self.config.enabled_layers and detections:
            self._render_bounding_boxes(draw, detections, font)

        if DebugLayer.HEATMAP in self.config.enabled_layers and heatmap:
            result = self._render_heatmap(result, heatmap)

        if DebugLayer.MOTION_VECTORS in self.config.enabled_layers and motion_vectors:
            self._render_motion_vectors(draw, motion_vectors)

        return result

    def _render_roi(
        self,
        draw: ImageDraw.ImageDraw,
        roi: tuple[int, int, int, int],
    ) -> None:
        """Render ROI border.

        Args:
            draw: PIL ImageDraw object.
            roi: ROI tuple.
        """
        left, top, right, bottom = roi
        draw.rectangle(
            [left, top, right, bottom],
            outline=self.config.roi_color,
            width=self.config.line_width,
        )

        # Label
        draw.text(
            (left + 5, top + 5),
            "Damage ROI",
            fill=self.config.roi_color,
            font=ImageFont.load_default(),
        )

    def _render_bounding_boxes(
        self,
        draw: ImageDraw.ImageDraw,
        detections: list[dict[str, Any]],
        font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    ) -> None:
        """Render bounding boxes for detections.

        Args:
            draw: PIL ImageDraw object.
            detections: List of detections.
            font: Font for labels.
        """
        for det in detections:
            # Get bounding box
            left = det.get("left", det.get("center_x", 0) - det.get("width", 40) // 2)
            top = det.get("top", det.get("center_y", 0) - det.get("height", 20) // 2)
            right = left + det.get("width", 40)
            bottom = top + det.get("height", 20)

            # Get color based on confidence
            confidence = det.get("confidence", 0.5)
            color = self.config.box_color_fn(confidence)

            # Draw box
            draw.rectangle(
                [left, top, right, bottom],
                outline=color,
                width=self.config.line_width,
            )

            # Draw label
            if self.config.show_text or self.config.show_confidence:
                labels = []
                if self.config.show_text:
                    labels.append(det.get("text", det.get("raw_text", "")))
                if self.config.show_confidence:
                    labels.append(f"{confidence:.2f}")

                label_text = " | ".join(labels)
                draw.text(
                    (left, top - self.config.font_size - 2),
                    label_text,
                    fill=color,
                    font=font,
                )

    def _render_heatmap(
        self,
        frame: Image.Image,
        heatmap: Image.Image,
    ) -> Image.Image:
        """Render heatmap overlay.

        Args:
            frame: Base frame.
            heatmap: Heatmap image.

        Returns:
            Frame with heatmap overlay.
        """
        # Blend heatmap with frame
        if heatmap.mode != "RGB":
            heatmap = heatmap.convert("RGB")

        result = Image.blend(frame, heatmap, alpha=0.5)
        return result

    def _render_motion_vectors(
        self,
        draw: ImageDraw.ImageDraw,
        vectors: list[tuple[float, float, float, float]],
    ) -> None:
        """Render motion vectors.

        Args:
            draw: PIL ImageDraw object.
            vectors: List of (x1, y1, x2, y2) vectors.
        """
        for x1, y1, x2, y2 in vectors:
            # Draw arrow
            draw.line([x1, y1, x2, y2], fill=(0, 255, 255), width=2)

            # Arrow head
            head_size = 8
            draw.line(
                [x2, y2, x2 - head_size, y2 - head_size],
                fill=(0, 255, 255),
                width=2,
            )
            draw.line(
                [x2, y2, x2 + head_size, y2 - head_size],
                fill=(0, 255, 255),
                width=2,
            )


def create_debug_viewer(
    title: str = "D4V Debug Viewer",
    width: int = 1920,
    height: int = 1080,
) -> Any:
    """Create debug viewer window (requires PySide6).

    Args:
        title: Window title.
        width: Window width.
        height: Window height.

    Returns:
        Debug viewer object or None.
    """
    try:
        from PySide6.QtWidgets import QApplication, QLabel, QMainWindow
        from PySide6.QtGui import QImage, QPixmap

        class DebugViewer(QMainWindow):
            """Debug viewer window."""

            def __init__(self, title: str, width: int, height: int):
                super().__init__()
                self.setWindowTitle(title)
                self.label = QLabel(self)
                self.setCentralWidget(self.label)
                self.resize(width, height)

            def update_frame(self, image: Image.Image) -> None:
                """Update displayed frame.

                Args:
                    image: PIL Image to display.
                """
                # Convert PIL to QImage
                rgb_image = image.convert("RGB")
                data = rgb_image.tobytes()
                qimage = QImage(data, image.width, image.height, QImage.Format_RGB888)
                pixmap = QPixmap.fromImage(qimage)
                self.label.setPixmap(pixmap)

        return DebugViewer(title, width, height)

    except ImportError:
        return None
