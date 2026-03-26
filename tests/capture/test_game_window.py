from d4v.capture.game_window import GameWindowBounds, is_diablo_iv_foreground


def test_bounds_width_and_height_are_positive():
    bounds = GameWindowBounds(left=10, top=20, width=300, height=200)
    assert bounds.width == 300
    assert bounds.height == 200


def test_is_diablo_iv_foreground_returns_bool():
    # Game does not need to be running — just verify the function returns a bool.
    result = is_diablo_iv_foreground()
    assert isinstance(result, bool)
