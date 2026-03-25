from d4v.vision.dedupe import dedupe_events


def test_dedupe_events_keeps_unique_hits():
    events = [
        {"frame": 1, "value": 1200},
        {"frame": 2, "value": 1200},
        {"frame": 5, "value": 9800},
    ]
    assert dedupe_events(events, frame_window=2) == [
        {"frame": 1, "value": 1200},
        {"frame": 5, "value": 9800},
    ]
