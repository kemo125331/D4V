from d4v.vision.damage_reader import DamageReader


def test_damage_reader_starts_with_no_events():
    reader = DamageReader()
    assert reader.read_events(None) == []
