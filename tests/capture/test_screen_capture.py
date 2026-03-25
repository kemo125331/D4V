from d4v.capture.screen_capture import normalize_roi


def test_normalize_roi_clamps_to_window():
    roi = normalize_roi((900, 900, 400, 300), window_size=(1024, 1024))
    assert roi == (900, 900, 124, 124)
