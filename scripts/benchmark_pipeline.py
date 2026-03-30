#!/usr/bin/env python3
"""CLI tool for running D4V detection benchmarks.

Usage:
    python scripts/benchmark_pipeline.py [--replay DIR] [--output FILE]

Examples:
    # Run all benchmarks in fixtures/benchmarks/
    python scripts/benchmark_pipeline.py

    # Run specific benchmark
    python scripts/benchmark_pipeline.py --replay fixtures/replays/session_001/frames

    # Save results to file
    python scripts/benchmark_pipeline.py --output results/benchmark_v1.json

    # Compare two benchmark runs
    python scripts/benchmark_pipeline.py --compare before.json after.json
"""

import argparse
import json
import sys
from pathlib import Path

from d4v.benchmark import (
    BenchmarkAnnotation,
    BenchmarkConfig,
    BenchmarkResult,
    BenchmarkRunner,
    compare_benchmark_results,
    load_benchmark_annotations,
)
from d4v.vision.config import VisionConfig


def cmd_run(args: argparse.Namespace) -> int:
    """Run benchmark command."""
    # Load annotations
    if args.annotation:
        annotations = [BenchmarkAnnotation.from_file(args.annotation)]
    else:
        annotations = load_benchmark_annotations(args.fixtures_dir)

    if not annotations:
        print("Error: No benchmark annotations found.")
        return 1

    print(f"Found {len(annotations)} benchmark annotation(s)")

    # Configure runner
    vision_config = VisionConfig(
        min_confidence=args.min_confidence,
        damage_roi=(args.roi_left, args.roi_top, args.roi_width, args.roi_height),
    )
    runner = BenchmarkRunner(vision_config=vision_config)

    # Configure benchmark
    benchmark_config = BenchmarkConfig(
        frame_tolerance=args.frame_tolerance,
        value_tolerance=args.value_tolerance,
        spatial_tolerance=args.spatial_tolerance,
        compute_per_frame=not args.no_per_frame,
        replay_frames_dir=Path(args.replay) if args.replay else None,
    )

    # Run benchmarks
    results: list[BenchmarkResult] = []
    for annotation in annotations:
        print(f"\n{'='*60}")
        print(f"Running: {annotation.session_name}")
        print(f"Session: {annotation.session_id}")
        print(f"Ground truth hits: {annotation.hit_count}")
        print("-" * 60)

        result = runner.run_benchmark(annotation, benchmark_config)
        results.append(result)

        print(f"Frames processed: {result.total_frames}")
        print(f"Detection time: {result.processing_time_seconds:.2f}s")
        print(f"Processing FPS: {result.fps_processed:.1f}")
        print(f"Detected hits: {result.total_detected_hits}")
        print()
        print(f"Precision:  {result.metrics.precision:6.2%}  ({result.metrics.true_positives} TP, {result.metrics.false_positives} FP)")
        print(f"Recall:     {result.metrics.recall:6.2%}  ({result.metrics.true_positives} TP, {result.metrics.false_negatives} FN)")
        print(f"F1 Score:   {result.metrics.f1_score:6.2%}")

        if result.errors:
            print(f"\nWarnings: {len(result.errors)} error(s)")
            for error in result.errors[:3]:
                print(f"  - {error}")

    # Save results
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if len(results) == 1:
            results[0].to_file(output_path)
        else:
            # Save multiple results as array
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump([r.to_dict() for r in results], f, indent=2)

        print(f"\nResults saved to: {output_path}")

    # Summary
    if len(results) > 1:
        avg_precision = sum(r.metrics.precision for r in results) / len(results)
        avg_recall = sum(r.metrics.recall for r in results) / len(results)
        avg_f1 = sum(r.metrics.f1_score for r in results) / len(results)

        print(f"\n{'='*60}")
        print(f"Summary ({len(results)} benchmarks)")
        print(f"Average Precision: {avg_precision:.2%}")
        print(f"Average Recall:    {avg_recall:.2%}")
        print(f"Average F1 Score:  {avg_f1:.2%}")

    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    """Compare two benchmark results."""
    before = BenchmarkResult.from_file(args.before)
    after = BenchmarkResult.from_file(args.after)

    comparison = compare_benchmark_results(before, after)

    print(f"Comparison: {comparison['session_id']}")
    print(f"{'='*60}")
    print()

    def format_metric(name: str, data: dict) -> None:
        delta = data["delta"]
        delta_str = f"{delta:+.2%}" if "precision" in name or "recall" in name or "f1" in name else f"{delta:+.1f}"
        pct = data["percent_change"]
        if pct == float("inf"):
            pct_str = "(+inf%)"
        else:
            pct_str = f"({pct:+.1f}%)"

        direction = "↑" if delta > 0 else "↓" if delta < 0 else "="
        print(f"{name:12} {data['before']:.4f} → {data['after']:.4f}  {delta_str} {pct_str} {direction}")

    format_metric("Precision", comparison["precision"])
    format_metric("Recall", comparison["recall"])
    format_metric("F1 Score", comparison["f1_score"])
    format_metric("FPS", comparison["fps_processed"])

    # Overall assessment
    f1_delta = comparison["f1_score"]["delta"]
    if f1_delta > 0.02:
        print(f"\n✓ Improvement: F1 score increased by {f1_delta:.2%}")
    elif f1_delta < -0.02:
        print(f"\n✗ Regression: F1 score decreased by {abs(f1_delta):.2%}")
    else:
        print(f"\n= No significant change: F1 score changed by {f1_delta:.2%}")

    return 0


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize a new benchmark annotation template."""
    from d4v.benchmark import AnnotationBuilder

    annotation = (
        AnnotationBuilder(session_id=args.session_id)
        .with_metadata(
            session_name=args.name or args.session_id,
            description=args.description or "Benchmark annotation",
            resolution=args.resolution,
            ui_scale=args.ui_scale,
            total_frames=args.total_frames,
            fps=args.fps,
        )
        .build()
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    annotation.to_file(output_path)

    print(f"Created benchmark annotation: {output_path}")
    print(f"Session ID: {annotation.session_id}")
    print(f"Edit the file to add ground truth hits.")
    return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="D4V Detection Benchmark Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run benchmark(s)")
    run_parser.add_argument(
        "--annotation", "-a",
        type=Path,
        help="Path to single benchmark annotation JSON file",
    )
    run_parser.add_argument(
        "--fixtures-dir", "-f",
        type=Path,
        default=Path(__file__).parent.parent / "fixtures" / "benchmarks",
        help="Directory containing benchmark JSON files",
    )
    run_parser.add_argument(
        "--replay", "-r",
        type=str,
        help="Directory containing replay frames (overrides annotation default)",
    )
    run_parser.add_argument(
        "--output", "-o",
        type=str,
        help="Output file for benchmark results (JSON)",
    )
    run_parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.6,
        help="Minimum confidence threshold for detection (default: 0.6)",
    )
    run_parser.add_argument(
        "--roi-left",
        type=float,
        default=0.15,
        help="ROI left offset as fraction (default: 0.15)",
    )
    run_parser.add_argument(
        "--roi-top",
        type=float,
        default=0.05,
        help="ROI top offset as fraction (default: 0.05)",
    )
    run_parser.add_argument(
        "--roi-width",
        type=float,
        default=0.70,
        help="ROI width as fraction (default: 0.70)",
    )
    run_parser.add_argument(
        "--roi-height",
        type=float,
        default=0.75,
        help="ROI height as fraction (default: 0.75)",
    )
    run_parser.add_argument(
        "--frame-tolerance",
        type=int,
        default=3,
        help="Frame tolerance for matching (default: 3)",
    )
    run_parser.add_argument(
        "--value-tolerance",
        type=float,
        default=0.1,
        help="Value tolerance for matching as fraction (default: 0.1 = 10%%)",
    )
    run_parser.add_argument(
        "--spatial-tolerance",
        type=float,
        default=70.0,
        help="Spatial tolerance for matching in pixels (default: 70)",
    )
    run_parser.add_argument(
        "--no-per-frame",
        action="store_true",
        help="Skip per-frame metrics calculation",
    )
    run_parser.set_defaults(func=cmd_run)

    # Compare command
    compare_parser = subparsers.add_parser("compare", help="Compare two benchmark results")
    compare_parser.add_argument("before", type=Path, help="Baseline benchmark result JSON")
    compare_parser.add_argument("after", type=Path, help="New benchmark result JSON")
    compare_parser.set_defaults(func=cmd_compare)

    # Init command
    init_parser = subparsers.add_parser("init", help="Initialize new benchmark annotation")
    init_parser.add_argument("session_id", type=str, help="Unique session identifier")
    init_parser.add_argument("--name", "-n", type=str, help="Human-readable session name")
    init_parser.add_argument("--description", "-d", type=str, help="Session description")
    init_parser.add_argument(
        "--resolution",
        type=str,
        default="1920x1080",
        help="Screen resolution (default: 1920x1080)",
    )
    init_parser.add_argument(
        "--ui-scale",
        type=float,
        default=100.0,
        help="UI scale percentage (default: 100)",
    )
    init_parser.add_argument(
        "--total-frames",
        type=int,
        default=1000,
        help="Total frames in replay (default: 1000)",
    )
    init_parser.add_argument(
        "--fps",
        type=float,
        default=30.0,
        help="Capture frame rate (default: 30)",
    )
    init_parser.add_argument(
        "--output", "-o",
        type=Path,
        required=True,
        help="Output file for annotation JSON",
    )
    init_parser.set_defaults(func=cmd_init)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
