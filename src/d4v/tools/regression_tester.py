"""Automated regression testing for detection pipeline.

Runs benchmarks on multiple scenarios and compares against baselines
to detect performance regressions.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from d4v.benchmark import BenchmarkAnnotation, load_benchmark_annotations
from d4v.benchmark.runner import (
    BenchmarkConfig,
    BenchmarkResult,
    BenchmarkRunner,
    compare_benchmark_results,
)
from d4v.profiling import PipelineProfiler
from d4v.vision.config import VisionConfig


@dataclass
class RegressionThresholds:
    """Thresholds for regression detection.

    Attributes:
        precision_min: Minimum acceptable precision.
        recall_min: Minimum acceptable recall.
        f1_min: Minimum acceptable F1 score.
        f1_max_drop: Maximum allowed F1 drop from baseline.
        latency_p95_max: Maximum P95 latency in ms.
        fps_min: Minimum acceptable FPS.
    """

    precision_min: float = 0.70
    recall_min: float = 0.70
    f1_min: float = 0.70
    f1_max_drop: float = 0.05  # 5% drop allowed
    latency_p95_max: float = 100.0  # ms
    fps_min: float = 25.0

    def to_dict(self) -> dict[str, float]:
        """Convert to dictionary."""
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
    """Result of regression test for a single scenario.

    Attributes:
        scenario_name: Name of test scenario.
        passed: Whether test passed.
        baseline_f1: Baseline F1 score.
        current_f1: Current F1 score.
        f1_change: Change in F1 score.
        baseline_precision: Baseline precision.
        current_precision: Current precision.
        baseline_recall: Baseline recall.
        current_recall: Current recall.
        current_latency_p95: Current P95 latency.
        current_fps: Current FPS.
        failures: List of failure reasons.
        warnings: List of warning messages.
    """

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
        """Convert to dictionary."""
        return {
            "scenario_name": self.scenario_name,
            "passed": self.passed,
            "baseline_f1": round(self.baseline_f1, 4) if self.baseline_f1 else None,
            "current_f1": round(self.current_f1, 4) if self.current_f1 else None,
            "f1_change": round(self.f1_change, 4) if self.f1_change else None,
            "baseline_precision": round(self.baseline_precision, 4) if self.baseline_precision else None,
            "current_precision": round(self.current_precision, 4) if self.current_precision else None,
            "baseline_recall": round(self.baseline_recall, 4) if self.baseline_recall else None,
            "current_recall": round(self.current_recall, 4) if self.current_recall else None,
            "current_latency_p95": round(self.current_latency_p95, 2) if self.current_latency_p95 else None,
            "current_fps": round(self.current_fps, 2) if self.current_fps else None,
            "failures": self.failures,
            "warnings": self.warnings,
        }


@dataclass
class RegressionReport:
    """Complete regression test report.

    Attributes:
        timestamp: Test run timestamp.
        vision_config_hash: Hash of vision configuration.
        thresholds: Thresholds used for testing.
        results: Results for each scenario.
        total_scenarios: Total number of scenarios tested.
        passed_scenarios: Number of scenarios that passed.
        failed_scenarios: Number of scenarios that failed.
        overall_passed: Whether all tests passed.
        summary: Overall summary message.
    """

    timestamp: str
    vision_config_hash: str
    thresholds: dict[str, float]
    results: list[RegressionResult]
    total_scenarios: int
    passed_scenarios: int
    failed_scenarios: int
    overall_passed: bool
    summary: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
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

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def to_markdown(self) -> str:
        """Generate Markdown report."""
        lines = [
            "# Regression Test Report",
            f"**Timestamp:** {self.timestamp}",
            f"**Overall:** {'✅ PASSED' if self.overall_passed else '❌ FAILED'}",
            "",
            "## Summary",
            f"- Total Scenarios: {self.total_scenarios}",
            f"- Passed: {self.passed_scenarios}",
            f"- Failed: {self.failed_scenarios}",
            "",
            "## Results by Scenario",
            "",
            "| Scenario | Status | F1 | Δ F1 | Precision | Recall | FPS |",
            "|----------|--------|-----|------|-----------|--------|-----|",
        ]

        for result in self.results:
            status = "✅" if result.passed else "❌"
            f1_str = f"{result.current_f1:.3f}" if result.current_f1 else "N/A"
            delta_str = f"{result.f1_change:+.3f}" if result.f1_change else "N/A"
            prec_str = f"{result.current_precision:.3f}" if result.current_precision else "N/A"
            rec_str = f"{result.current_recall:.3f}" if result.current_recall else "N/A"
            fps_str = f"{result.current_fps:.1f}" if result.current_fps else "N/A"

            lines.append(
                f"| {result.scenario_name} | {status} | {f1_str} | {delta_str} | {prec_str} | {rec_str} | {fps_str} |"
            )

        if any(r.failures for r in self.results):
            lines.extend(["", "## Failures", ""])
            for result in self.results:
                if result.failures:
                    lines.append(f"### {result.scenario_name}")
                    for failure in result.failures:
                        lines.append(f"- ❌ {failure}")

        if any(r.warnings for r in self.results):
            lines.extend(["", "## Warnings", ""])
            for result in self.results:
                if result.warnings:
                    lines.append(f"### {result.scenario_name}")
                    for warning in result.warnings:
                        lines.append(f"- ⚠️ {warning}")

        return "\n".join(lines)


class RegressionTester:
    """Automated regression testing for detection pipeline.

    Example:
        tester = RegressionTester(
            baseline_dir=Path("baselines"),
            thresholds=RegressionThresholds(f1_min=0.75),
        )

        # Run regression tests
        report = tester.run_regression_tests(
            fixtures_dir=Path("fixtures/replays"),
            annotations_dir=Path("fixtures/benchmarks"),
        )

        # Check results
        if not report.overall_passed:
            print("Regression detected!")
            for result in report.results:
                if not result.passed:
                    print(f"  {result.scenario_name}: {result.failures}")

        # Save report
        report.to_file(Path("reports/regression_2026-03-30.json"))
    """

    def __init__(
        self,
        baseline_dir: Path | str | None = None,
        thresholds: RegressionThresholds | None = None,
        vision_config: VisionConfig | None = None,
    ) -> None:
        """Initialize regression tester.

        Args:
            baseline_dir: Directory for baseline results.
            thresholds: Regression detection thresholds.
            vision_config: Vision configuration for testing.
        """
        self.baseline_dir = Path(baseline_dir) if baseline_dir else Path("baselines")
        self.thresholds = thresholds or RegressionThresholds()
        self.vision_config = vision_config or VisionConfig()
        self.runner = BenchmarkRunner(vision_config=self.vision_config)

    def run_regression_tests(
        self,
        fixtures_dir: Path | str,
        annotations_dir: Path | str | None = None,
        save_baseline: bool = False,
    ) -> RegressionReport:
        """Run regression tests on all scenarios.

        Args:
            fixtures_dir: Directory containing replay frames.
            annotations_dir: Directory containing benchmark annotations.
            save_baseline: Whether to save results as new baseline.

        Returns:
            RegressionReport with all test results.
        """
        fixtures_dir = Path(fixtures_dir)
        annotations_dir = Path(annotations_dir) if annotations_dir else fixtures_dir.parent / "benchmarks"

        # Load annotations
        annotations = load_benchmark_annotations(annotations_dir)

        if not annotations:
            return RegressionReport(
                timestamp=datetime.now().isoformat(),
                vision_config_hash=self._config_hash(),
                thresholds=self.thresholds.to_dict(),
                results=[],
                total_scenarios=0,
                passed_scenarios=0,
                failed_scenarios=0,
                overall_passed=True,
                summary="No benchmark annotations found",
            )

        # Run benchmarks
        results: list[RegressionResult] = []
        for annotation in annotations:
            result = self._test_scenario(annotation, fixtures_dir)
            results.append(result)

        # Calculate summary
        passed = sum(1 for r in results if r.passed)
        failed = len(results) - passed

        report = RegressionReport(
            timestamp=datetime.now().isoformat(),
            vision_config_hash=self._config_hash(),
            thresholds=self.thresholds.to_dict(),
            results=results,
            total_scenarios=len(results),
            passed_scenarios=passed,
            failed_scenarios=failed,
            overall_passed=failed == 0,
            summary=f"{passed}/{len(results)} scenarios passed",
        )

        # Save baseline if requested
        if save_baseline:
            self._save_baselines(results)

        return report

    def _test_scenario(
        self,
        annotation: BenchmarkAnnotation,
        fixtures_dir: Path,
    ) -> RegressionResult:
        """Test a single scenario.

        Args:
            annotation: Benchmark annotation.
            fixtures_dir: Directory containing replay frames.

        Returns:
            RegressionResult for the scenario.
        """
        result = RegressionResult(scenario_name=annotation.session_name)

        # Run benchmark
        config = BenchmarkConfig(
            replay_frames_dir=fixtures_dir / annotation.session_id / "frames",
        )

        try:
            benchmark_result = self.runner.run_benchmark(annotation, config)
        except Exception as e:
            result.failures.append(f"Benchmark execution failed: {e}")
            return result

        # Set current metrics
        result.current_f1 = benchmark_result.metrics.f1_score
        result.current_precision = benchmark_result.metrics.precision
        result.current_recall = benchmark_result.metrics.recall
        result.current_fps = benchmark_result.fps_processed

        # Load baseline
        baseline = self._load_baseline(annotation.session_id)

        if baseline:
            result.baseline_f1 = baseline.get("f1_score")
            result.baseline_precision = baseline.get("precision")
            result.baseline_recall = baseline.get("recall")

            if result.baseline_f1 and result.current_f1:
                result.f1_change = result.current_f1 - result.baseline_f1

        # Check thresholds
        self._check_thresholds(result)

        return result

    def _check_thresholds(self, result: RegressionResult) -> None:
        """Check if results meet thresholds.

        Args:
            result: RegressionResult to check.
        """
        # Check F1 score
        if result.current_f1 is not None:
            if result.current_f1 < self.thresholds.f1_min:
                result.failures.append(
                    f"F1 score {result.current_f1:.3f} below minimum {self.thresholds.f1_min}"
                )

            # Check F1 drop from baseline
            if result.baseline_f1 is not None and result.f1_change is not None:
                if result.f1_change < -self.thresholds.f1_max_drop:
                    result.failures.append(
                        f"F1 dropped by {abs(result.f1_change):.3f} (max allowed: {self.thresholds.f1_max_drop})"
                    )
                elif result.f1_change < 0:
                    result.warnings.append(
                        f"F1 decreased by {abs(result.f1_change):.3f}"
                    )

        # Check precision
        if result.current_precision is not None:
            if result.current_precision < self.thresholds.precision_min:
                result.failures.append(
                    f"Precision {result.current_precision:.3f} below minimum {self.thresholds.precision_min}"
                )

        # Check recall
        if result.current_recall is not None:
            if result.current_recall < self.thresholds.recall_min:
                result.failures.append(
                    f"Recall {result.current_recall:.3f} below minimum {self.thresholds.recall_min}"
                )

        # Check FPS
        if result.current_fps is not None:
            if result.current_fps < self.thresholds.fps_min:
                result.failures.append(
                    f"FPS {result.current_fps:.1f} below minimum {self.thresholds.fps_min}"
                )
            elif result.current_fps < self.thresholds.fps_min * 1.1:
                result.warnings.append(
                    f"FPS {result.current_fps:.1f} close to minimum {self.thresholds.fps_min}"
                )

        # Set pass/fail
        result.passed = len(result.failures) == 0

    def _load_baseline(self, scenario_id: str) -> dict[str, float] | None:
        """Load baseline results for a scenario.

        Args:
            scenario_id: Scenario identifier.

        Returns:
            Baseline metrics dictionary or None.
        """
        baseline_path = self.baseline_dir / f"{scenario_id}.json"
        if not baseline_path.exists():
            return None

        with open(baseline_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data.get("metrics", {})

    def _save_baselines(self, results: list[RegressionResult]) -> None:
        """Save results as new baselines.

        Args:
            results: List of regression results.
        """
        self.baseline_dir.mkdir(parents=True, exist_ok=True)

        for result in results:
            baseline_data = {
                "scenario_name": result.scenario_name,
                "timestamp": datetime.now().isoformat(),
                "metrics": {
                    "f1_score": result.current_f1,
                    "precision": result.current_precision,
                    "recall": result.current_recall,
                    "fps": result.current_fps,
                },
            }

            baseline_path = self.baseline_dir / f"{result.scenario_name.replace(' ', '_')}.json"
            with open(baseline_path, "w", encoding="utf-8") as f:
                json.dump(baseline_data, f, indent=2)

    def _config_hash(self) -> str:
        """Generate hash of vision configuration.

        Returns:
            Configuration hash string.
        """
        import hashlib
        config_str = str(self.vision_config.__dict__)
        return hashlib.md5(config_str.encode()).hexdigest()[:8]


def run_regression_cli(
    fixtures_dir: Path,
    baseline_dir: Path | None = None,
    output_path: Path | None = None,
    save_baseline: bool = False,
    thresholds: dict[str, float] | None = None,
) -> int:
    """Run regression tests from command line.

    Args:
        fixtures_dir: Directory containing test fixtures.
        baseline_dir: Directory for baseline results.
        output_path: Path for report output.
        save_baseline: Whether to save baselines.
        thresholds: Custom thresholds.

    Returns:
        Exit code (0 = passed, 1 = failed).
    """
    if thresholds:
        regression_thresholds = RegressionThresholds(**thresholds)
    else:
        regression_thresholds = RegressionThresholds()

    tester = RegressionTester(
        baseline_dir=baseline_dir,
        thresholds=regression_thresholds,
    )

    print("Running regression tests...")
    report = tester.run_regression_tests(
        fixtures_dir=fixtures_dir,
        save_baseline=save_baseline,
    )

    # Print summary
    print("\n" + "=" * 60)
    print(report.summary)
    print("=" * 60)

    for result in report.results:
        status = "✅ PASS" if result.passed else "❌ FAIL"
        print(f"\n{result.scenario_name}: {status}")
        if result.current_f1:
            print(f"  F1: {result.current_f1:.3f}", end="")
            if result.f1_change is not None:
                print(f" ({result.f1_change:+.3f})", end="")
            print()
        if result.failures:
            for failure in result.failures:
                print(f"  ❌ {failure}")
        if result.warnings:
            for warning in result.warnings:
                print(f"  ⚠️ {warning}")

    # Save report
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report.to_json())
        print(f"\nReport saved to: {output_path}")

        # Also save Markdown
        md_path = output_path.with_suffix(".md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(report.to_markdown())
        print(f"Markdown report saved to: {md_path}")

    return 0 if report.overall_passed else 1


if __name__ == "__main__":
    # Run from command line
    import argparse

    parser = argparse.ArgumentParser(description="Run regression tests")
    parser.add_argument(
        "--fixtures", "-f",
        type=Path,
        default=Path("fixtures/replays"),
        help="Fixtures directory",
    )
    parser.add_argument(
        "--baseline", "-b",
        type=Path,
        default=Path("baselines"),
        help="Baseline directory",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("reports/regression_test.json"),
        help="Output report path",
    )
    parser.add_argument(
        "--save-baseline",
        action="store_true",
        help="Save results as new baseline",
    )

    args = parser.parse_args()

    exit_code = run_regression_cli(
        fixtures_dir=args.fixtures,
        baseline_dir=args.baseline,
        output_path=args.output,
        save_baseline=args.save_baseline,
    )

    sys.exit(exit_code)
