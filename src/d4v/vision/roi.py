from dataclasses import dataclass


@dataclass(frozen=True)
class Roi:
    left: int
    top: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height


def scale_relative_roi(
    image_size: tuple[int, int],
    relative_roi: tuple[float, float, float, float],
) -> Roi:
    image_width, image_height = image_size
    left, top, width, height = relative_roi
    return Roi(
        left=int(image_width * left),
        top=int(image_height * top),
        width=int(image_width * width),
        height=int(image_height * height),
    )
