"""Training data extraction from existing replay analysis.

Extracts features and labels from existing replay analysis JSON files
to train the ML confidence classifier.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from d4v.benchmark import AnnotationBuilder, BenchmarkAnnotation, GroundTruthHit
from d4v.vision.confidence_model import ConfidenceFeatures, ConfidenceTrainingData


@dataclass
class ExtractedSample:
    """Sample extracted from replay analysis.

    Attributes:
        features: Feature dictionary.
        label: 1 for hit, 0 for miss.
        source: Source file and entry.
    """

    features: dict[str, Any]
    label: int
    source: str


def load_replay_analysis(analysis_path: Path | str) -> dict[str, Any]:
    """Load replay analysis JSON file.

    Args:
        analysis_path: Path to analysis summary.json.

    Returns:
        Analysis data dictionary.
    """
    analysis_path = Path(analysis_path)
    with open(analysis_path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_features_from_result(result: dict[str, Any]) -> dict[str, Any]:
    """Extract ML features from OCR result entry.

    Args:
        result: OCR result dictionary from analysis.

    Returns:
        Feature dictionary.
    """
    # Calculate additional features
    width = result.get("right", 0) - result.get("left", 0)
    height = result.get("bottom", 0) - result.get("top", 0)
    area = width * height
    aspect_ratio = width / max(height, 1)

    # Estimate fill ratio from score (higher score = better fill)
    score = result.get("score", 5.0)
    fill_ratio = min(score / 12.0, 1.0)  # Normalize to 0-1

    raw_text = result.get("raw_text", "")
    parsed_value = result.get("parsed_value")

    return {
        "line_score": score,
        "fill_ratio": fill_ratio,
        "aspect_ratio": aspect_ratio,
        "member_count": 1,  # Not available in analysis, estimate
        "width": width,
        "height": height,
        "has_digit": any(c.isdigit() for c in raw_text) if raw_text else False,
        "has_suffix": any(c in raw_text.upper() for c in "KMB") if raw_text else False,
        "has_decimal": "." in raw_text if raw_text else False,
        "starts_with_nonzero": (raw_text and raw_text[0].isdigit() and raw_text[0] != '0') if raw_text else False,
        "text_length": len(raw_text) if raw_text else 0,
        "parsed_value": parsed_value,
        "value_in_range": 100 <= parsed_value <= 100_000_000 if parsed_value else False,
        "is_plausible": result.get("is_plausible", False),
    }


def extract_samples_from_analysis(
    analysis_path: Path | str,
    confident_threshold: float = 0.6,
) -> list[ExtractedSample]:
    """Extract training samples from replay analysis.

    Uses confident detections as positive samples (hits) and
    low-confidence/unrecognized as negative samples (misses).

    Args:
        analysis_path: Path to analysis summary.json.
        confident_threshold: Confidence threshold for positive labels.

    Returns:
        List of ExtractedSample objects.
    """
    analysis = load_replay_analysis(analysis_path)
    samples: list[ExtractedSample] = []

    results = analysis.get("results", [])
    for result in results:
        features = extract_features_from_result(result)
        confidence = result.get("confidence", 0.0)
        is_confident = result.get("is_confident", False)
        is_plausible = result.get("is_plausible", False)

        # Label based on confidence and plausibility
        if is_confident and is_plausible and confidence >= confident_threshold:
            label = 1  # Positive: confirmed hit
        elif confidence < 0.3 or not is_plausible:
            label = 0  # Negative: likely false positive
        else:
            continue  # Skip ambiguous samples

        samples.append(
            ExtractedSample(
                features=features,
                label=label,
                source=f"{analysis_path}:{result.get('frame_name', 'unknown')}",
            )
        )

    return samples


def extract_stable_hits_as_ground_truth(
    analysis_path: Path | str,
) -> list[GroundTruthHit]:
    """Extract stable hits as ground truth annotations.

    Args:
        analysis_path: Path to analysis summary.json.

    Returns:
        List of GroundTruthHit objects.
    """
    analysis = load_replay_analysis(analysis_path)
    hits: list[GroundTruthHit] = []

    stable_hits = analysis.get("stable_hits", [])
    for hit in stable_hits:
        ground_truth = GroundTruthHit(
            frame=hit.get("frame_index", 0),
            value=hit.get("parsed_value", 0),
            x=hit.get("center_x", 0),
            y=hit.get("center_y", 0),
            damage_type="direct",  # Default, could be enhanced
        )
        hits.append(ground_truth)

    return hits


def create_benchmark_annotation_from_analysis(
    analysis_path: Path | str,
    session_id: str | None = None,
) -> BenchmarkAnnotation:
    """Create benchmark annotation from replay analysis.

    Args:
        analysis_path: Path to analysis summary.json.
        session_id: Session ID (auto-generated if None).

    Returns:
        BenchmarkAnnotation object.
    """
    analysis = load_replay_analysis(analysis_path)
    metadata = analysis.get("metadata", {})

    # Extract ground truth hits
    ground_truth_hits = extract_stable_hits_as_ground_truth(analysis_path)

    # Create annotation
    builder = AnnotationBuilder(
        session_id=session_id or Path(analysis_path).parent.parent.name
    )

    builder = builder.with_metadata(
        session_name=metadata.get("session_name", "Unknown"),
        description=f"Auto-generated from replay analysis",
        resolution="1920x1080",  # Default, could be detected
        ui_scale=100.0,
        total_frames=metadata.get("frames_written", 0),
        fps=metadata.get("fps", 10.0),
    )

    for hit in ground_truth_hits:
        builder = builder.add_hit(
            frame=hit.frame,
            value=hit.value,
            x=hit.x,
            y=hit.y,
            damage_type=hit.damage_type,
        )

    return builder.build()


def extract_all_replays(
    replays_dir: Path | str,
    output_dir: Path | str | None = None,
) -> tuple[ConfidenceTrainingData, list[BenchmarkAnnotation]]:
    """Extract training data from all replay analyses.

    Args:
        replays_dir: Directory containing replay folders.
        output_dir: Output directory for annotations.

    Returns:
        Tuple of (training_data, benchmark_annotations).
    """
    replays_dir = Path(replays_dir)
    training_data = ConfidenceTrainingData()
    benchmark_annotations: list[BenchmarkAnnotation] = []

    # Find all analysis summary files
    analysis_files = list(replays_dir.glob("*/analysis/combat-ocr/summary.json"))

    print(f"Found {len(analysis_files)} replay analyses")

    for analysis_path in analysis_files:
        session_id = analysis_path.parent.parent.parent.name

        print(f"\nProcessing: {session_id}")

        # Extract training samples
        try:
            samples = extract_samples_from_analysis(analysis_path)
            print(f"  Extracted {len(samples)} training samples")

            for sample in samples:
                features = ConfidenceFeatures(**sample.features)
                training_data.samples.append((features, sample.label))

            # Create benchmark annotation
            annotation = create_benchmark_annotation_from_analysis(
                analysis_path, session_id=session_id
            )
            benchmark_annotations.append(annotation)
            print(f"  Created annotation with {annotation.hit_count} hits")

        except Exception as e:
            print(f"  Error processing {session_id}: {e}")

    # Save benchmark annotations
    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        for annotation in benchmark_annotations:
            annotation_path = output_path / f"{annotation.session_id}.json"
            annotation.to_file(annotation_path)

        print(f"\nSaved {len(benchmark_annotations)} annotations to {output_path}")

    return training_data, benchmark_annotations


def generate_training_report(
    training_data: ConfidenceTrainingData,
    output_path: Path | str | None = None,
) -> dict[str, Any]:
    """Generate training data quality report.

    Args:
        training_data: Training data object.
        output_path: Optional path to save report.

    Returns:
        Report dictionary.
    """
    stats = training_data.get_statistics()

    # Analyze feature distributions
    features, labels = training_data.get_features_and_labels()

    positive_features = [f for f, l in zip(features, labels) if l == 1]
    negative_features = [f for f, l in zip(features, labels) if l == 0]

    report = {
        "total_samples": stats["total"],
        "positive_samples": stats["positive"],
        "negative_samples": stats["negative"],
        "positive_ratio": stats["positive_ratio"],
        "class_balance": "balanced" if 0.3 <= stats["positive_ratio"] <= 0.7 else "imbalanced",
        "avg_confidence_positive": (
            sum(f.line_score for f in positive_features) / len(positive_features)
            if positive_features else 0
        ),
        "avg_confidence_negative": (
            sum(f.line_score for f in negative_features) / len(negative_features)
            if negative_features else 0
        ),
    }

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

    return report


def main():
    """Main entry point for training data extraction."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Extract training data from replay analysis"
    )
    parser.add_argument(
        "--replays-dir",
        type=Path,
        default=Path("fixtures/replays"),
        help="Directory containing replay folders",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("fixtures/benchmarks"),
        help="Output directory for benchmark annotations",
    )
    parser.add_argument(
        "--training-output",
        type=Path,
        default=Path("fixtures/training_data.json"),
        help="Output path for training data JSON",
    )
    parser.add_argument(
        "--report-output",
        type=Path,
        default=Path("reports/training_report.json"),
        help="Output path for training report",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("D4V Training Data Extraction")
    print("=" * 60)

    # Extract all replays
    training_data, annotations = extract_all_replays(
        args.replays_dir,
        args.output_dir,
    )

    # Save training data
    training_data.export(args.training_output)
    print(f"\nSaved training data to {args.training_output}")

    # Generate report
    report = generate_training_report(training_data, args.report_output)
    print(f"\nTraining Data Report:")
    print(f"  Total samples: {report['total_samples']}")
    print(f"  Positive: {report['positive_samples']} ({report['positive_ratio']:.1%})")
    print(f"  Negative: {report['negative_samples']}")
    print(f"  Class balance: {report['class_balance']}")
    print(f"\nSaved report to {args.report_output}")

    print("\n" + "=" * 60)
    print("Next steps:")
    print("1. Review training report for class balance")
    print("2. If imbalanced, adjust confident_threshold")
    print("3. Train ML model: python scripts/train_confidence_model.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
