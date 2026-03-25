import json

from d4v.tools.analyze_candidates import analyze_candidates, load_candidates


def test_analyze_candidates_sums_damage_and_categories(tmp_path):
    path = tmp_path / "candidates.json"
    path.write_text(
        json.dumps(
            [
                {"text": "12,500", "frame": 1, "timestamp_ms": 100},
                {"text": "35 Gold", "frame": 2, "timestamp_ms": 120},
                {"text": "Ancestral Helm", "frame": 3, "timestamp_ms": 140},
            ]
        ),
        encoding="utf-8",
    )

    summary = analyze_candidates(load_candidates(path))

    assert summary.total_candidates == 3
    assert summary.parsed_damage_total == 12500
    assert summary.category_counts["damage"] == 1
    assert summary.category_counts["gold"] == 1
    assert summary.category_counts["item"] == 1
