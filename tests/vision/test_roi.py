from d4v.vision.roi import Roi, scale_relative_roi


def test_scale_relative_roi_maps_to_absolute_pixels():
    roi = scale_relative_roi((1000, 800), (0.2, 0.1, 0.4, 0.5))
    assert roi == Roi(left=200, top=80, width=400, height=400)
