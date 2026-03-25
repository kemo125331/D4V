from d4v.capture.game_window import GameWindowBounds


def test_bounds_width_and_height_are_positive():
    bounds = GameWindowBounds(left=10, top=20, width=300, height=200)
    assert bounds.width == 300
    assert bounds.height == 200
