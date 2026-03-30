#!/usr/bin/env python3
"""Train ML confidence classifier from extracted training data.

Usage:
    # First extract training data
    python scripts/extract_training_data.py

    # Then train the model
    python scripts/train_confidence_model.py

    # Or train with custom parameters
    python scripts/train_confidence_model.py \
        --training-data fixtures/training_data.json \
        --output models/confidence_model.joblib \
        --test-split 0.2
"""

import argparse
import json
import sys
from pathlib import Path


def load_training_data(training_path: Path | str) -> tuple[list, list]:
    """Load training data from JSON file.

    Args:
        training_path: Path to training data JSON.

    Returns:
        Tuple of (features, labels).
    """
    training_path = Path(training_path)
    with open(training_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    samples = data.get("samples", [])
    features = []
    labels = []

    for sample in samples:
        features.append(sample.get("features", {}))
        labels.append(sample.get("label", 0))

    return features, labels


def train_model(
    features: list[dict],
    labels: list[int],
    test_split: float = 0.2,
    random_state: int = 42,
) -> dict:
    """Train logistic regression model.

    Args:
        features: List of feature dictionaries.
        labels: List of labels (0 or 1).
        test_split: Fraction of data for testing.
        random_state: Random seed for reproducibility.

    Returns:
        Training results dictionary.
    """
    try:
        import numpy as np
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import (
            accuracy_score,
            classification_report,
            confusion_matrix,
            f1_score,
            precision_score,
            recall_score,
        )
        from sklearn.model_selection import train_test_split
        from sklearn.preprocessing import StandardScaler
    except ImportError:
        print("Error: scikit-learn is required")
        print("Install with: pip install scikit-learn")
        return {}

    # Convert features to array
    feature_names = [
        "line_score",
        "fill_ratio",
        "aspect_ratio",
        "member_count",
        "width",
        "height",
        "has_digit",
        "has_suffix",
        "has_decimal",
        "starts_with_nonzero",
        "text_length",
        "parsed_value",
        "value_in_range",
        "is_plausible",
    ]

    X = np.array([
        [f.get(name, 0) or 0 for name in feature_names]
        for f in features
    ])
    y = np.array(labels)

    # Handle None values
    X = np.nan_to_num(X, nan=0.0)

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_split, random_state=random_state, stratify=y
    )

    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Train model
    print("Training logistic regression model...")
    model = LogisticRegression(
        max_iter=1000,
        class_weight="balanced",
        random_state=random_state,
        solver="lbfgs",
    )
    model.fit(X_train_scaled, y_train)

    # Evaluate
    y_pred = model.predict(X_test_scaled)

    results = {
        "accuracy": accuracy_score(y_test, y_pred),
        "precision": precision_score(y_test, y_pred, zero_division=0),
        "recall": recall_score(y_test, y_pred, zero_division=0),
        "f1": f1_score(y_test, y_pred, zero_division=0),
        "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
        "feature_names": feature_names,
        "feature_coefficients": model.coef_[0].tolist(),
        "intercept": model.intercept_[0],
        "train_size": len(y_train),
        "test_size": len(y_test),
    }

    print("\n" + "=" * 60)
    print("Training Results")
    print("=" * 60)
    print(f"Train size: {len(y_train)}")
    print(f"Test size: {len(y_test)}")
    print(f"\nAccuracy:  {results['accuracy']:.2%}")
    print(f"Precision: {results['precision']:.2%}")
    print(f"Recall:    {results['recall']:.2%}")
    print(f"F1 Score:  {results['f1']:.2%}")
    print("\nConfusion Matrix:")
    print(f"  {results['confusion_matrix']}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=["miss", "hit"]))

    print("\nFeature Importance:")
    for name, coef in sorted(
        zip(feature_names, model.coef_[0]), key=lambda x: abs(x[1]), reverse=True
    )[:10]:
        print(f"  {name:20} {coef:>8.4f}")

    return results


def save_model(model, scaler, feature_names: list, output_path: Path) -> None:
    """Save trained model to file.

    Args:
        model: Trained model.
        scaler: Feature scaler.
        feature_names: List of feature names.
        output_path: Output path.
    """
    try:
        import joblib
    except ImportError:
        print("Error: joblib is required")
        print("Install with: pip install joblib")
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)

    package = {
        "model": model,
        "scaler": scaler,
        "feature_names": feature_names,
    }

    joblib.dump(package, output_path)
    print(f"\nModel saved to: {output_path}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Train ML confidence classifier"
    )
    parser.add_argument(
        "--training-data",
        type=Path,
        default=Path("fixtures/training_data.json"),
        help="Path to training data JSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("models/confidence_model.joblib"),
        help="Output path for trained model",
    )
    parser.add_argument(
        "--test-split",
        type=float,
        default=0.2,
        help="Fraction of data for testing (0.0-1.0)",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Random seed for reproducibility",
    )
    parser.add_argument(
        "--report-output",
        type=Path,
        default=Path("reports/training_results.json"),
        help="Output path for training results",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("D4V ML Confidence Classifier Training")
    print("=" * 60)

    # Check if training data exists
    if not args.training_data.exists():
        print(f"\nError: Training data not found: {args.training_data}")
        print("\nFirst run: python scripts/extract_training_data.py")
        sys.exit(1)

    # Load training data
    print(f"\nLoading training data from {args.training_data}...")
    features, labels = load_training_data(args.training_data)

    if not features:
        print("Error: No training data found")
        sys.exit(1)

    print(f"Loaded {len(features)} samples")
    print(f"  Positive (hits): {sum(labels)}")
    print(f"  Negative (misses): {len(labels) - sum(labels)}")

    # Train model
    results = train_model(features, labels, args.test_split, args.random_state)

    if not results:
        sys.exit(1)

    # Save results
    results_path = args.report_output
    results_path.parent.mkdir(parents=True, exist_ok=True)
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {results_path}")

    # Save model
    try:
        import joblib
        from sklearn.preprocessing import StandardScaler

        # Re-train on full data for final model
        feature_names = results["feature_names"]
        X = [[f.get(name, 0) or 0 for name in feature_names] for f in features]
        import numpy as np
        X = np.nan_to_num(np.array(X), nan=0.0)

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        from sklearn.linear_model import LogisticRegression
        model = LogisticRegression(
            max_iter=1000,
            class_weight="balanced",
            random_state=args.random_state,
            solver="lbfgs",
        )
        model.fit(X_scaled, labels)

        save_model(model, scaler, feature_names, args.output)

    except ImportError:
        print("\nNote: Model not saved (scikit-learn or joblib not available)")

    print("\n" + "=" * 60)
    print("Training complete!")
    print("\nTo use the model:")
    print("  from d4v.vision.confidence_model import ConfidenceClassifier")
    print(f"  classifier = ConfidenceClassifier(model_path='{args.output}')")
    print("=" * 60)


if __name__ == "__main__":
    main()
