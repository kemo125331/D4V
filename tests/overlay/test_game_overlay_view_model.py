from d4v.overlay.game_overlay import GameOverlayViewModel, format_elapsed_time


def test_format_elapsed_time_uses_minutes_and_seconds():
    assert format_elapsed_time(0) == "00:00"
    assert format_elapsed_time(65_000) == "01:05"


def test_game_overlay_view_model_formats_peak_and_timer():
    view_model = GameOverlayViewModel.from_stats(
        avg_damage=12345,
        last_damage=67890,
        total_damage=120000,
        hits_count=9,
        dps=3210,
        peak_hit=99999,
        elapsed_ms=95_000,
    )

    assert view_model.avg_damage_label == "12.3K"
    assert view_model.last_damage_label == "67.9K"
    assert view_model.peak_hit_label == "100K"
    assert view_model.session_time_label == "01:35"
