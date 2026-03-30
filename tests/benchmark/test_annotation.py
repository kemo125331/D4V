"""Tests for benchmark annotation format and helpers."""

import json
import tempfile
from pathlib import Path

import pytest

from d4v.benchmark.annotation import (
    AnnotationBuilder,
    BenchmarkAnnotation,
    GroundTruthHit,
    load_benchmark_annotations,
    save_benchmark_annotations,
)


class TestGroundTruthHit:
    """Tests for GroundTruthHit dataclass."""

    def test_create_hit(self):
        """Given valid parameters, expect hit created."""
        hit = GroundTruthHit(frame=10, value=1234, x=500, y=300)
        assert hit.frame == 10
        assert hit.value == 1234
        assert hit.x == 500
        assert hit.y == 300
        assert hit.damage_type == "direct"
        assert hit.notes == ""

    def test_to_dict(self):
        """Given hit, expect dict with all fields."""
        hit = GroundTruthHit(
            frame=10,
            value=1234,
            x=500,
            y=300,
            width=50,
            height=20,
            damage_type="crit",
            notes="Big hit",
        )
        result = hit.to_dict()
        assert result["frame"] == 10
        assert result["value"] == 1234
        assert result["x"] == 500
        assert result["y"] == 300
        assert result["width"] == 50
        assert result["height"] == 20
        assert result["damage_type"] == "crit"
        assert result["notes"] == "Big hit"

    def test_from_dict(self):
        """Given dict, expect hit created."""
        data = {
            "frame": 10,
            "value": 1234,
            "x": 500,
            "y": 300,
            "width": 50,
            "height": 20,
            "damage_type": "crit",
            "notes": "Big hit",
        }
        hit = GroundTruthHit.from_dict(data)
        assert hit.frame == 10
        assert hit.value == 1234
        assert hit.damage_type == "crit"

    def test_from_dict_defaults(self):
        """Given dict with missing optional fields, expect defaults."""
        data = {"frame": 10, "value": 1234, "x": 500, "y": 300}
        hit = GroundTruthHit.from_dict(data)
        assert hit.width == 0
        assert hit.height == 0
        assert hit.damage_type == "direct"
        assert hit.notes == ""


class TestBenchmarkAnnotation:
    """Tests for BenchmarkAnnotation dataclass."""

    def test_create_annotation(self):
        """Given valid parameters, expect annotation created."""
        hits = [
            GroundTruthHit(frame=10, value=1000, x=500, y=300),
            GroundTruthHit(frame=20, value=2000, x=600, y=400),
        ]
        annotation = BenchmarkAnnotation(
            session_id="session_001",
            session_name="Test Combat",
            description="Test session",
            resolution="1920x1080",
            ui_scale=100.0,
            total_frames=1000,
            fps=30.0,
            hits=hits,
        )
        assert annotation.session_id == "session_001"
        assert annotation.hit_count == 2
        assert annotation.total_damage == 3000

    def test_to_dict(self):
        """Given annotation, expect dict with all fields."""
        hits = [GroundTruthHit(frame=10, value=1000, x=500, y=300)]
        annotation = BenchmarkAnnotation(
            session_id="session_001",
            session_name="Test",
            description="Test session",
            resolution="1920x1080",
            ui_scale=100.0,
            total_frames=1000,
            fps=30.0,
            hits=hits,
            metadata={"build": "test"},
        )
        result = annotation.to_dict()
        assert result["session_id"] == "session_001"
        assert len(result["hits"]) == 1
        assert result["metadata"]["build"] == "test"

    def test_to_json(self):
        """Given annotation, expect valid JSON string."""
        hits = [GroundTruthHit(frame=10, value=1000, x=500, y=300)]
        annotation = BenchmarkAnnotation(
            session_id="session_001",
            session_name="Test",
            description="Test",
            resolution="1920x1080",
            ui_scale=100.0,
            total_frames=1000,
            fps=30.0,
            hits=hits,
        )
        json_str = annotation.to_json()
        data = json.loads(json_str)
        assert data["session_id"] == "session_001"

    def test_from_json(self):
        """Given JSON string, expect annotation reconstructed."""
        json_str = """
        {
            "session_id": "session_001",
            "session_name": "Test",
            "description": "Test session",
            "resolution": "1920x1080",
            "ui_scale": 100.0,
            "total_frames": 1000,
            "fps": 30.0,
            "hits": [
                {"frame": 10, "value": 1000, "x": 500, "y": 300}
            ]
        }
        """
        annotation = BenchmarkAnnotation.from_json(json_str)
        assert annotation.session_id == "session_001"
        assert annotation.hit_count == 1

    def test_from_file_and_to_file(self):
        """Given file path, expect load and save work."""
        hits = [GroundTruthHit(frame=10, value=1000, x=500, y=300)]
        annotation = BenchmarkAnnotation(
            session_id="session_001",
            session_name="Test",
            description="Test",
            resolution="1920x1080",
            ui_scale=100.0,
            total_frames=1000,
            fps=30.0,
            hits=hits,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.json"
            annotation.to_file(path)
            loaded = BenchmarkAnnotation.from_file(path)
            assert loaded.session_id == "session_001"
            assert loaded.hit_count == 1

    def test_get_hits_for_frame(self):
        """Given frame index, expect matching hits."""
        hits = [
            GroundTruthHit(frame=10, value=1000, x=500, y=300),
            GroundTruthHit(frame=10, value=1500, x=550, y=350),
            GroundTruthHit(frame=20, value=2000, x=600, y=400),
        ]
        annotation = BenchmarkAnnotation(
            session_id="session_001",
            session_name="Test",
            description="Test",
            resolution="1920x1080",
            ui_scale=100.0,
            total_frames=1000,
            fps=30.0,
            hits=hits,
        )
        frame_10_hits = annotation.get_hits_for_frame(10)
        assert len(frame_10_hits) == 2

        frame_20_hits = annotation.get_hits_for_frame(20)
        assert len(frame_20_hits) == 1

    def test_get_hits_for_frame_with_tolerance(self):
        """Given frame with tolerance, expect nearby hits."""
        hits = [
            GroundTruthHit(frame=10, value=1000, x=500, y=300),
            GroundTruthHit(frame=11, value=1500, x=550, y=350),
            GroundTruthHit(frame=12, value=2000, x=600, y=400),
        ]
        annotation = BenchmarkAnnotation(
            session_id="session_001",
            session_name="Test",
            description="Test",
            resolution="1920x1080",
            ui_scale=100.0,
            total_frames=1000,
            fps=30.0,
            hits=hits,
        )
        # With tolerance=2, should get frames 10, 11, 12
        hits = annotation.get_hits_for_frame(11, tolerance=2)
        assert len(hits) == 3


class TestAnnotationBuilder:
    """Tests for AnnotationBuilder."""

    def test_builder_basic(self):
        """Given builder with minimal calls, expect annotation created."""
        annotation = (
            AnnotationBuilder(session_id="session_001")
            .with_metadata(
                session_name="Test",
                description="Test session",
                resolution="1920x1080",
                ui_scale=100.0,
                total_frames=1000,
                fps=30.0,
            )
            .build()
        )
        assert annotation.session_id == "session_001"
        assert annotation.session_name == "Test"
        assert annotation.hit_count == 0

    def test_builder_add_hit(self):
        """Given builder with add_hit, expect hit in annotation."""
        annotation = (
            AnnotationBuilder(session_id="session_001")
            .with_metadata(
                session_name="Test",
                description="Test",
                resolution="1920x1080",
                ui_scale=100.0,
                total_frames=1000,
                fps=30.0,
            )
            .add_hit(frame=10, value=1000, x=500, y=300)
            .build()
        )
        assert annotation.hit_count == 1
        assert annotation.hits[0].value == 1000

    def test_builder_add_multiple_hits(self):
        """Given builder with multiple add_hit calls, expect all hits."""
        annotation = (
            AnnotationBuilder(session_id="session_001")
            .with_metadata(
                session_name="Test",
                description="Test",
                resolution="1920x1080",
                ui_scale=100.0,
                total_frames=1000,
                fps=30.0,
            )
            .add_hit(frame=10, value=1000, x=500, y=300)
            .add_hit(frame=20, value=2000, x=600, y=400, damage_type="crit")
            .add_hit(frame=30, value=3000, x=700, y=500)
            .build()
        )
        assert annotation.hit_count == 3
        assert annotation.total_damage == 6000

    def test_builder_add_hits_from_list(self):
        """Given builder with add_hits_from_list, expect all hits added."""
        hits_data = [
            {"frame": 10, "value": 1000, "x": 500, "y": 300},
            {"frame": 20, "value": 2000, "x": 600, "y": 400},
            {"frame": 30, "value": 3000, "x": 700, "y": 500},
        ]
        annotation = (
            AnnotationBuilder(session_id="session_001")
            .with_metadata(
                session_name="Test",
                description="Test",
                resolution="1920x1080",
                ui_scale=100.0,
                total_frames=1000,
                fps=30.0,
            )
            .add_hits_from_list(hits_data)
            .build()
        )
        assert annotation.hit_count == 3

    def test_builder_with_metadata_dict(self):
        """Given builder with metadata_dict, expect extra metadata."""
        annotation = (
            AnnotationBuilder(session_id="session_001")
            .with_metadata(
                session_name="Test",
                description="Test",
                resolution="1920x1080",
                ui_scale=100.0,
                total_frames=1000,
                fps=30.0,
            )
            .add_hit(frame=10, value=1000, x=500, y=300)
            .with_metadata_dict({"build": "test", "zone": "zone1"})
            .build()
        )
        assert annotation.metadata is not None
        assert annotation.metadata["build"] == "test"
        assert annotation.metadata["zone"] == "zone1"

    def test_builder_method_chaining(self):
        """Given builder, expect all methods return self for chaining."""
        builder = AnnotationBuilder(session_id="session_001")
        assert builder.with_metadata() is builder
        assert builder.add_hit(frame=0, value=0, x=0, y=0) is builder
        assert builder.add_hits_from_list([]) is builder
        assert builder.with_metadata_dict({}) is builder


class TestLoadSaveBenchmarkAnnotations:
    """Tests for loading and saving multiple annotations."""

    def test_save_and_load_annotations(self):
        """Given annotations saved, expect load returns them."""
        hits = [GroundTruthHit(frame=10, value=1000, x=500, y=300)]
        annotation = BenchmarkAnnotation(
            session_id="benchmark_v1",
            session_name="Test Benchmark",
            description="Test",
            resolution="1920x1080",
            ui_scale=100.0,
            total_frames=1000,
            fps=30.0,
            hits=hits,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            save_benchmark_annotations([annotation], tmpdir_path)
            loaded = load_benchmark_annotations(tmpdir_path)
            assert len(loaded) == 1
            assert loaded[0].session_id == "benchmark_v1"

    def test_load_nonexistent_directory(self):
        """Given non-existent directory, expect empty list."""
        annotations = load_benchmark_annotations("/nonexistent/path")
        assert len(annotations) == 0

    def test_load_only_benchmark_files(self):
        """Given directory with mixed files, expect only benchmark_*.json loaded."""
        hits = [GroundTruthHit(frame=10, value=1000, x=500, y=300)]
        annotation = BenchmarkAnnotation(
            session_id="benchmark_v1",
            session_name="Test",
            description="Test",
            resolution="1920x1080",
            ui_scale=100.0,
            total_frames=1000,
            fps=30.0,
            hits=hits,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            # Save benchmark file
            save_benchmark_annotations([annotation], tmpdir_path)
            # Create non-benchmark file
            other_file = tmpdir_path / "other.json"
            other_file.write_text('{"not": "a benchmark"}')

            loaded = load_benchmark_annotations(tmpdir_path)
            assert len(loaded) == 1
            assert loaded[0].session_id == "benchmark_v1"
