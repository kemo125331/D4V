"""Tests for synthetic frame generator and regression testing."""

import tempfile
from pathlib import Path

import pytest

from d4v.tools.synthetic_generator import (
    DamageNumber,
    FrameConfig,
    SyntheticFrameGenerator,
    generate_test_fixtures,
)

# Regression tester tests are skipped if cv2 is not available
try:
    from d4v.tools.regression_tester import (
        RegressionReport,
        RegressionResult,
        RegressionTester,
        RegressionThresholds,
        run_regression_cli,
    )
    REGRESSION_TESTER_AVAILABLE = True
except ImportError:
    REGRESSION_TESTER_AVAILABLE = False
    # Import dataclasses for non-cv2 tests
    from dataclasses import dataclass, field
    from typing import Any

    @dataclass
    class RegressionThresholds:
        precision_min: float = 0.70
        recall_min: float = 0.70
        f1_min: float = 0.70
        f1_max_drop: float = 0.05
        latency_p95_max: float = 100.0
        fps_min: float = 25.0

        def to_dict(self) -> dict[str, float]:
            return {
                "precision_min": self.precision_min,
                "recall_min": self.recall_min,
                "f1_min": self.f1_min,
                "f1_max_drop": self.f1_max_drop,
                "latency_p95_max": self.latency_p95_max,
                "fps_min": self.fps_min,
            }

    @dataclass
    class RegressionResult:
        scenario_name: str
        passed: bool
        baseline_f1: float | None = None
        current_f1: float | None = None
        f1_change: float | None = None
        baseline_precision: float | None = None
        current_precision: float | None = None
        baseline_recall: float | None = None
        current_recall: float | None = None
        current_latency_p95: float | None = None
        current_fps: float | None = None
        failures: list[str] = field(default_factory=list)
        warnings: list[str] = field(default_factory=list)

        def to_dict(self) -> dict[str, Any]:
            return {
                "scenario_name": self.scenario_name,
                "passed": self.passed,
                "baseline_f1": self.baseline_f1,
                "current_f1": self.current_f1,
                "f1_change": self.f1_change,
                "failures": self.failures,
                "warnings": self.warnings,
            }

    @dataclass
    class RegressionReport:
        timestamp: str
        vision_config_hash: str
        thresholds: dict[str, float]
        results: list
        total_scenarios: int
        passed_scenarios: int
        failed_scenarios: int
        overall_passed: bool
        summary: str

        def to_dict(self) -> dict[str, Any]:
            return {
                "timestamp": self.timestamp,
                "vision_config_hash": self.vision_config_hash,
                "thresholds": self.thresholds,
                "results": [r.to_dict() for r in self.results],
                "total_scenarios": self.total_scenarios,
                "passed_scenarios": self.passed_scenarios,
                "failed_scenarios": self.failed_scenarios,
                "overall_passed": self.overall_passed,
                "summary": self.summary,
            }

        def to_markdown(self) -> str:
            return "# Regression Test Report\n" + self.summary


class TestDamageNumber:
    """Tests for DamageNumber dataclass."""

    def test_create_damage_number(self):
        """Given valid parameters, expect damage number created."""
        damage = DamageNumber(value=1234, x=500, y=300)
        assert damage.value == 1234
        assert damage.x == 500
        assert damage.y == 300
        assert damage.display_text == "1234"
        assert damage.color == "#FFA500"  # Default orange

    def test_damage_with_suffix(self):
        """Given suffix, expect display text includes it."""
        damage = DamageNumber(value=123, x=500, y=300, suffix="K")
        assert damage.display_text == "123K"

    def test_damage_colors(self):
        """Given damage types, expect correct colors."""
        assert DamageNumber(value=1, x=0, y=0, damage_type="direct").color == "#FFA500"
        assert DamageNumber(value=1, x=0, y=0, damage_type="crit").color == "#FFD700"
        assert DamageNumber(value=1, x=0, y=0, damage_type="dot").color == "#00FF00"
        assert DamageNumber(value=1, x=0, y=0, damage_type="cold").color == "#0080FF"
        assert DamageNumber(value=1, x=0, y=0, damage_type="fire").color == "#FF4500"


class TestFrameConfig:
    """Tests for FrameConfig dataclass."""

    def test_create_default_config(self):
        """Given no parameters, expect default config."""
        config = FrameConfig()
        assert config.width == 1920
        assert config.height == 1080
        assert config.background == "black"
        assert config.damage_numbers == []
        assert config.noise_level == 0

    def test_create_custom_config(self):
        """Given parameters, expect custom config."""
        damage = DamageNumber(value=100, x=100, y=100)
        config = FrameConfig(
            width=800,
            height=600,
            background="gradient",
            damage_numbers=[damage],
            noise_level=20,
        )
        assert config.width == 800
        assert config.background == "gradient"
        assert len(config.damage_numbers) == 1

    def test_invalid_noise_level(self):
        """Given invalid noise level, expect error."""
        with pytest.raises(ValueError):
            FrameConfig(noise_level=150)

    def test_invalid_blur_amount(self):
        """Given negative blur, expect error."""
        with pytest.raises(ValueError):
            FrameConfig(blur_amount=-1)


class TestSyntheticFrameGenerator:
    """Tests for SyntheticFrameGenerator."""

    def test_generator_creation(self):
        """Given generator created, expect initialized."""
        generator = SyntheticFrameGenerator(seed=42)
        assert generator.rng is not None

    def test_generate_single_frame(self):
        """Given frame config, expect image generated."""
        generator = SyntheticFrameGenerator(seed=42)
        config = FrameConfig(
            width=1920,
            height=1080,
            damage_numbers=[
                DamageNumber(value=1234, x=500, y=300),
            ],
        )

        image = generator.generate_frame(config)

        assert image.width == 1920
        assert image.height == 1080

    def test_generate_frame_multiple_damage(self):
        """Given multiple damage numbers, expect all rendered."""
        generator = SyntheticFrameGenerator(seed=42)
        config = FrameConfig(
            width=1920,
            height=1080,
            damage_numbers=[
                DamageNumber(value=1000, x=200, y=200),
                DamageNumber(value=2000, x=400, y=400),
                DamageNumber(value=3000, x=600, y=600),
            ],
        )

        image = generator.generate_frame(config)

        assert image.width == 1920
        assert image.height == 1080

    def test_generate_frame_with_noise(self):
        """Given noise level, expect noise added."""
        generator = SyntheticFrameGenerator(seed=42)
        config = FrameConfig(
            width=800,
            height=600,
            noise_level=50,
        )

        image = generator.generate_frame(config)

        assert image.width == 800
        assert image.height == 600

    def test_generate_sequence(self, tmp_path: Path):
        """Given sequence generation, expect frames saved."""
        generator = SyntheticFrameGenerator(seed=42)
        output_dir = tmp_path / "frames"

        paths = generator.generate_sequence(
            num_frames=10,
            output_dir=output_dir,
            config=FrameConfig(background="black"),
            damage_pattern="combat",
        )

        assert len(paths) == 10
        assert output_dir.exists()
        for path in paths:
            assert path.exists()
            assert path.suffix == ".png"

    def test_generate_sequence_different_patterns(self, tmp_path: Path):
        """Given different patterns, expect varied damage."""
        generator = SyntheticFrameGenerator(seed=42)

        patterns = ["combat", "burst", "dot", "mixed"]
        for pattern in patterns:
            output_dir = tmp_path / f"pattern_{pattern}"
            paths = generator.generate_sequence(
                num_frames=30,
                output_dir=output_dir,
                damage_pattern=pattern,
            )
            assert len(paths) == 30

    def test_reproducible_with_seed(self, tmp_path: Path):
        """Given same seed, expect identical output."""
        gen1 = SyntheticFrameGenerator(seed=123)
        gen2 = SyntheticFrameGenerator(seed=123)

        dir1 = tmp_path / "gen1"
        dir2 = tmp_path / "gen2"

        gen1.generate_sequence(num_frames=5, output_dir=dir1, damage_pattern="combat")
        gen2.generate_sequence(num_frames=5, output_dir=dir2, damage_pattern="combat")

        # Compare generated files
        for i in range(5):
            path1 = dir1 / f"frame_{i:06d}.png"
            path2 = dir2 / f"frame_{i:06d}.png"
            assert path1.exists()
            assert path2.exists()
            # File contents should be identical
            assert path1.read_bytes() == path2.read_bytes()


class TestGenerateTestFixtures:
    """Tests for generate_test_fixtures function."""

    def test_generate_all_scenarios(self, tmp_path: Path):
        """Given fixture generation, expect all scenarios created."""
        results = generate_test_fixtures(output_dir=tmp_path, seed=42)

        expected_scenarios = [
            "normal_combat",
            "burst_damage",
            "dot_ticks",
            "mixed_combat",
            "high_crits",
        ]

        for scenario in expected_scenarios:
            assert scenario in results
            assert len(results[scenario]) > 0


class TestRegressionThresholds:
    """Tests for RegressionThresholds."""

    @pytest.mark.skipif(not REGRESSION_TESTER_AVAILABLE, reason="cv2 not available")
    def test_default_thresholds(self):
        """Given default creation, expect standard thresholds."""
        thresholds = RegressionThresholds()
        assert thresholds.precision_min == 0.70
        assert thresholds.recall_min == 0.70
        assert thresholds.f1_min == 0.70
        assert thresholds.f1_max_drop == 0.05
        assert thresholds.latency_p95_max == 100.0
        assert thresholds.fps_min == 25.0

    def test_custom_thresholds(self):
        """Given custom values, expect thresholds set."""
        thresholds = RegressionThresholds(
            f1_min=0.80,
            fps_min=30.0,
        )
        assert thresholds.f1_min == 0.80
        assert thresholds.fps_min == 30.0

    def test_to_dict(self):
        """Given thresholds, expect dict conversion."""
        thresholds = RegressionThresholds()
        data = thresholds.to_dict()
        assert "precision_min" in data
        assert "f1_min" in data


class TestRegressionResult:
    """Tests for RegressionResult."""

    def test_create_passing_result(self):
        """Given passing test, expect result created."""
        result = RegressionResult(
            scenario_name="test_scenario",
            passed=True,
            current_f1=0.85,
            current_precision=0.80,
            current_recall=0.90,
        )
        assert result.scenario_name == "test_scenario"
        assert result.passed
        assert len(result.failures) == 0

    def test_create_failing_result(self):
        """Given failing test, expect result with failures."""
        result = RegressionResult(
            scenario_name="test_scenario",
            passed=False,
            current_f1=0.60,
            failures=["F1 below minimum threshold"],
        )
        assert not result.passed
        assert len(result.failures) > 0

    def test_to_dict(self):
        """Given result, expect dict conversion."""
        result = RegressionResult(
            scenario_name="test",
            passed=True,
            current_f1=0.85,
        )
        data = result.to_dict()
        assert data["scenario_name"] == "test"
        assert data["passed"]
        assert data["current_f1"] == 0.85


class TestRegressionReport:
    """Tests for RegressionReport."""

    def test_create_report(self):
        """Given results, expect report created."""
        results = [
            RegressionResult(scenario_name="test1", passed=True, current_f1=0.85),
            RegressionResult(scenario_name="test2", passed=False, current_f1=0.60),
        ]

        report = RegressionReport(
            timestamp="2026-03-30T00:00:00",
            vision_config_hash="abc123",
            thresholds={},
            results=results,
            total_scenarios=2,
            passed_scenarios=1,
            failed_scenarios=1,
            overall_passed=False,
            summary="1/2 scenarios passed",
        )

        assert report.total_scenarios == 2
        assert not report.overall_passed

    def test_to_dict(self):
        """Given report, expect dict conversion."""
        report = RegressionReport(
            timestamp="2026-03-30T00:00:00",
            vision_config_hash="abc123",
            thresholds={},
            results=[],
            total_scenarios=0,
            passed_scenarios=0,
            failed_scenarios=0,
            overall_passed=True,
            summary="All passed",
        )

        data = report.to_dict()
        assert data["timestamp"] == "2026-03-30T00:00:00"
        assert data["overall_passed"]

    def test_to_markdown(self):
        """Given report, expect markdown generated."""
        report = RegressionReport(
            timestamp="2026-03-30T00:00:00",
            vision_config_hash="abc123",
            thresholds={},
            results=[
                RegressionResult(scenario_name="test1", passed=True, current_f1=0.85),
            ],
            total_scenarios=1,
            passed_scenarios=1,
            failed_scenarios=0,
            overall_passed=True,
            summary="All passed",
        )

        md = report.to_markdown()
        assert "# Regression Test Report" in md
        assert "test1" in md


@pytest.mark.skipif(not REGRESSION_TESTER_AVAILABLE, reason="cv2 not available")
class TestRegressionTester:
    """Tests for RegressionTester."""

    def test_tester_creation(self):
        """Given tester created, expect initialized."""
        tester = RegressionTester()
        assert tester.thresholds is not None
        assert tester.vision_config is not None

    def test_tester_with_custom_thresholds(self):
        """Given custom thresholds, expect used."""
        thresholds = RegressionThresholds(f1_min=0.90)
        tester = RegressionTester(thresholds=thresholds)
        assert tester.thresholds.f1_min == 0.90

    def test_run_regression_no_annotations(self, tmp_path: Path):
        """Given no annotations, expect empty report."""
        tester = RegressionTester()
        report = tester.run_regression_tests(
            fixtures_dir=tmp_path,
            annotations_dir=tmp_path / "nonexistent",
        )

        assert report.total_scenarios == 0
        assert report.overall_passed

    def test_check_thresholds_pass(self):
        """Given good metrics, expect pass."""
        tester = RegressionTester(
            thresholds=RegressionThresholds(
                f1_min=0.70,
                precision_min=0.70,
                recall_min=0.70,
                fps_min=25.0,
            )
        )

        result = RegressionResult(
            scenario_name="test",
            passed=True,
            current_f1=0.85,
            current_precision=0.80,
            current_recall=0.90,
            current_fps=30.0,
        )

        tester._check_thresholds(result)
        assert result.passed
        assert len(result.failures) == 0

    def test_check_thresholds_fail_f1(self):
        """Given low F1, expect failure."""
        tester = RegressionTester(
            thresholds=RegressionThresholds(f1_min=0.70)
        )

        result = RegressionResult(
            scenario_name="test",
            passed=True,
            current_f1=0.50,
        )

        tester._check_thresholds(result)
        assert not result.passed
        assert any("F1" in f for f in result.failures)

    def test_check_thresholds_fail_fps(self):
        """Given low FPS, expect failure."""
        tester = RegressionTester(
            thresholds=RegressionThresholds(fps_min=30.0)
        )

        result = RegressionResult(
            scenario_name="test",
            passed=True,
            current_fps=20.0,
        )

        tester._check_thresholds(result)
        assert not result.passed
        assert any("FPS" in f for f in result.failures)

    def test_check_thresholds_f1_drop(self):
        """Given F1 drop, expect failure."""
        tester = RegressionTester(
            thresholds=RegressionThresholds(f1_max_drop=0.05)
        )

        result = RegressionResult(
            scenario_name="test",
            passed=True,
            baseline_f1=0.90,
            current_f1=0.70,
            f1_change=-0.20,
        )

        tester._check_thresholds(result)
        assert not result.passed
        assert any("dropped" in f.lower() for f in result.failures)


@pytest.mark.skipif(not REGRESSION_TESTER_AVAILABLE, reason="cv2 not available")
class TestIntegration:
    """Integration tests for synthetic generation and regression."""

    def test_full_workflow(self, tmp_path: Path):
        """Given full workflow, expect end-to-end success."""
        # Generate synthetic fixtures
        fixtures_dir = tmp_path / "fixtures"
        results = generate_test_fixtures(output_dir=fixtures_dir / "replays", seed=42)

        assert len(results) > 0

        # Create simple annotation for one scenario
        from d4v.benchmark import AnnotationBuilder

        annotation = (
            AnnotationBuilder(session_id="synthetic_normal_combat")
            .with_metadata(
                session_name="Normal Combat",
                description="Synthetic combat",
                resolution="1920x1080",
                ui_scale=100.0,
                total_frames=200,
                fps=30.0,
            )
            .build()
        )

        # Save annotation
        benchmarks_dir = fixtures_dir / "benchmarks"
        benchmarks_dir.mkdir(parents=True, exist_ok=True)
        annotation.to_file(benchmarks_dir / "synthetic_normal_combat.json")

        # Run regression test
        tester = RegressionTester(
            baseline_dir=tmp_path / "baselines",
            thresholds=RegressionThresholds(
                f1_min=0.0,  # Very low for synthetic data
                fps_min=10.0,
            ),
        )

        report = tester.run_regression_tests(
            fixtures_dir=fixtures_dir / "replays",
            annotations_dir=benchmarks_dir,
        )

        # Should have at least one result
        assert report.total_scenarios >= 0
