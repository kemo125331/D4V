import json
from pathlib import Path

import pytest

from d4v.overlay.config import OverlayConfig, load_overlay_config, save_overlay_config


class TestOverlayConfigDefaults:
    def test_default_opacity(self):
        config = OverlayConfig()
        assert config.opacity == 0.85

    def test_default_font_size(self):
        config = OverlayConfig()
        assert config.font_size == 14

    def test_default_text_color(self):
        config = OverlayConfig()
        assert config.text_color == "#00ff00"

    def test_default_bg_color(self):
        config = OverlayConfig()
        assert config.bg_color == "#1a1a1a"

    def test_default_click_through(self):
        config = OverlayConfig()
        assert config.click_through is True

    def test_default_position(self):
        config = OverlayConfig()
        assert config.position is None

    def test_default_font_family(self):
        config = OverlayConfig()
        assert config.font_family == "Segoe UI"

    def test_default_title_color(self):
        config = OverlayConfig()
        assert config.title_color == "#888888"

    def test_default_label_color(self):
        config = OverlayConfig()
        assert config.label_color == "#666666"

    def test_default_separator_color(self):
        config = OverlayConfig()
        assert config.separator_color == "#333333"

    def test_default_mode(self):
        config = OverlayConfig()
        assert config.mode == "expanded"


class TestOverlayConfigCustomValues:
    def test_custom_values_stored(self):
        config = OverlayConfig(
            opacity=0.5,
            font_size=20,
            text_color="#ffffff",
            bg_color="#000000",
            click_through=False,
            position=(100, 200),
            font_family="Arial",
            title_color="#aaaaaa",
            label_color="#bbbbbb",
            separator_color="#cccccc",
            mode="compact",
        )
        assert config.opacity == 0.5
        assert config.font_size == 20
        assert config.text_color == "#ffffff"
        assert config.bg_color == "#000000"
        assert config.click_through is False
        assert config.position == (100, 200)
        assert config.font_family == "Arial"
        assert config.title_color == "#aaaaaa"
        assert config.label_color == "#bbbbbb"
        assert config.separator_color == "#cccccc"
        assert config.mode == "compact"


class TestSaveOverlayConfig:
    def test_save_config_to_file(self, tmp_path: Path):
        config = OverlayConfig(opacity=0.5, font_size=20)
        path = tmp_path / "config.json"
        save_overlay_config(config, path)
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["opacity"] == 0.5
        assert data["font_size"] == 20

    def test_save_default_config(self, tmp_path: Path):
        config = OverlayConfig()
        path = tmp_path / "config.json"
        save_overlay_config(config, path)
        data = json.loads(path.read_text())
        assert data["opacity"] == 0.85
        assert data["font_size"] == 14


class TestLoadOverlayConfig:
    def test_load_config_from_file(self, tmp_path: Path):
        data = {
            "opacity": 0.7,
            "font_size": 18,
            "text_color": "#ff0000",
            "bg_color": "#222222",
            "click_through": False,
            "position": [50, 100],
            "font_family": "Consolas",
            "title_color": "#999999",
            "label_color": "#777777",
            "separator_color": "#444444",
            "mode": "compact",
        }
        path = tmp_path / "config.json"
        path.write_text(json.dumps(data))
        config = load_overlay_config(path)
        assert config.opacity == 0.7
        assert config.font_size == 18
        assert config.text_color == "#ff0000"
        assert config.bg_color == "#222222"
        assert config.click_through is False
        assert config.position == (50, 100)
        assert config.font_family == "Consolas"
        assert config.title_color == "#999999"
        assert config.label_color == "#777777"
        assert config.separator_color == "#444444"
        assert config.mode == "compact"


class TestSaveLoadRoundTrip:
    def test_round_trip_preserves_values(self, tmp_path: Path):
        original = OverlayConfig(
            opacity=0.6,
            font_size=16,
            text_color="#aabbcc",
            bg_color="#ddeeff",
            click_through=False,
            position=(300, 400),
            font_family="Verdana",
            title_color="#111111",
            label_color="#222222",
            separator_color="#333333",
            mode="compact",
        )
        path = tmp_path / "config.json"
        save_overlay_config(original, path)
        loaded = load_overlay_config(path)
        assert loaded.opacity == original.opacity
        assert loaded.font_size == original.font_size
        assert loaded.text_color == original.text_color
        assert loaded.bg_color == original.bg_color
        assert loaded.click_through == original.click_through
        assert loaded.position == original.position
        assert loaded.font_family == original.font_family
        assert loaded.title_color == original.title_color
        assert loaded.label_color == original.label_color
        assert loaded.separator_color == original.separator_color
        assert loaded.mode == original.mode

    def test_round_trip_with_none_position(self, tmp_path: Path):
        original = OverlayConfig(position=None)
        path = tmp_path / "config.json"
        save_overlay_config(original, path)
        loaded = load_overlay_config(path)
        assert loaded.position is None


class TestMissingConfigFile:
    def test_load_returns_defaults_when_file_missing(self, tmp_path: Path):
        path = tmp_path / "nonexistent.json"
        config = load_overlay_config(path)
        assert config == OverlayConfig()

    def test_load_returns_defaults_for_nonexistent_default_path(self):
        config = load_overlay_config()
        assert config == OverlayConfig()

    def test_default_path_uses_appdata(self, monkeypatch, tmp_path: Path):
        monkeypatch.setenv("APPDATA", str(tmp_path))
        config = OverlayConfig(opacity=0.5)
        save_overlay_config(config)
        loaded = load_overlay_config()
        assert loaded.opacity == 0.5
        assert (tmp_path / "D4V" / "overlay_config.json").exists()


class TestCorruptConfigFile:
    def test_load_returns_defaults_on_invalid_json(self, tmp_path: Path):
        path = tmp_path / "config.json"
        path.write_text("not valid json {{{")
        config = load_overlay_config(path)
        assert config == OverlayConfig()

    def test_load_returns_defaults_on_empty_file(self, tmp_path: Path):
        path = tmp_path / "config.json"
        path.write_text("")
        config = load_overlay_config(path)
        assert config == OverlayConfig()


class TestPositionHandling:
    def test_position_tuple_saved_as_list(self, tmp_path: Path):
        config = OverlayConfig(position=(100, 200))
        path = tmp_path / "config.json"
        save_overlay_config(config, path)
        data = json.loads(path.read_text())
        assert data["position"] == [100, 200]

    def test_position_list_loaded_as_tuple(self, tmp_path: Path):
        data = {"position": [100, 200]}
        path = tmp_path / "config.json"
        path.write_text(json.dumps(data))
        config = load_overlay_config(path)
        assert config.position == (100, 200)
        assert isinstance(config.position, tuple)


class TestConfigDirectoryCreation:
    def test_config_directory_created_if_missing(self, tmp_path: Path):
        config = OverlayConfig(opacity=0.5)
        nested_dir = tmp_path / "subdir" / "nested"
        path = nested_dir / "config.json"
        save_overlay_config(config, path)
        assert path.exists()
        loaded = load_overlay_config(path)
        assert loaded.opacity == 0.5
