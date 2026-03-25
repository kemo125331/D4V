from d4v.overlay.view_model import PreviewViewModel, format_damage_value


def test_format_damage_value_uses_grouping_and_precision():
    assert format_damage_value(12500) == "12,500"
    assert format_damage_value(1234.5) == "1,234.50"


def test_preview_view_model_formats_labels():
    view_model = PreviewViewModel.from_state(
        total_damage=12500,
        rolling_dps=3456.78,
        biggest_hit=9800,
        last_hit=1200,
        status="Running replay",
    )

    assert view_model.total_damage_label == "12,500"
    assert view_model.rolling_dps_label == "3,456.78"
    assert view_model.biggest_hit_label == "9,800"
    assert view_model.last_hit_label == "1,200"
    assert view_model.status_label == "Running replay"
