from d4v.domain.session_stats import SessionStats


def test_session_stats_updates_total_and_peak():
    stats = SessionStats()
    stats.add_hit(frame=1, timestamp_ms=1000, value=1200)
    stats.add_hit(frame=2, timestamp_ms=1200, value=9800)
    assert stats.visible_damage_total == 11000
    assert stats.peak_hit == 9800
    assert stats.hit_count == 2
    assert stats.biggest_hit == 9800
    assert stats.average_hit == 5500


def test_session_stats_tracks_rolling_damage_window():
    stats = SessionStats()
    stats.add_hit(frame=1, timestamp_ms=0, value=1000)
    stats.add_hit(frame=2, timestamp_ms=1000, value=2000)
    stats.add_hit(frame=3, timestamp_ms=7001, value=500)
    assert stats.rolling_damage(window_ms=5000) == 500


def test_session_stats_reset_clears_totals():
    stats = SessionStats()
    stats.add_hit(frame=1, timestamp_ms=0, value=1000)
    stats.reset()

    assert stats.visible_damage_total == 0
    assert stats.peak_hit == 0
    assert stats.hit_count == 0
    assert stats.average_hit == 0.0
    assert stats.rolling_damage() == 0
