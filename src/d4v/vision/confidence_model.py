"""ML-based confidence scoring for detection candidates.

Replaces heuristic confidence scoring with a trained classifier
for more accurate hit/no-hit decisions.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal


def _is_plausible_damage_text(text: str) -> bool:
    """Check if text looks like valid damage number.

    Args:
        text: OCR text to check.

    Returns:
        True if text looks like damage number.
    """
    if not text:
        return False

    # Must contain at least one digit
    if not any(c.isdigit() for c in text):
        return False

    # Check for plausible patterns
    # Pure digits: 1234
    if re.match(r'^\d+$', text):
        return True

    # Digits with suffix: 1234K, 12.3M
    if re.match(r'^\d+(\.\d+)?[KMBkmb]$', text):
        return True

    # Decimal: 12.34
    if re.match(r'^\d+\.\d+$', text):
        return True

    return False


def _parse_damage_value(text: str) -> int | None:
    """Parse damage value from text.

    Args:
        text: OCR text containing damage value.

    Returns:
        Parsed integer value, or None if parsing failed.
    """
    if not text:
        return None

    text = text.strip().upper()

    # Multipliers for suffixes
    multipliers = {'K': 1000, 'M': 1000000, 'B': 1000000000}

    # Check for suffix
    for suffix, mult in multipliers.items():
        if text.endswith(suffix):
            try:
                num_str = text[:-1]
                value = float(num_str)
                return int(value * mult)
            except ValueError:
                return None

    # No suffix - parse as integer or float
    try:
        return int(float(text))
    except ValueError:
        return None


@dataclass(frozen=True)
class ConfidenceFeatures:
    """Features for confidence classification.

    Attributes:
        line_score: Heuristic line score from vision pipeline.
        fill_ratio: Ratio of text pixels to bounding box area.
        aspect_ratio: Width/height ratio of bounding box.
        member_count: Number of connected components.
        width: Bounding box width in pixels.
        height: Bounding box height in pixels.
        has_digit: Whether text contains digits.
        has_suffix: Whether text contains K/M/B suffix.
        has_decimal: Whether text contains decimal point.
        starts_with_nonzero: Whether text starts with non-zero digit.
        text_length: Length of OCR text.
        parsed_value: Parsed damage value (or None).
        value_in_range: Whether parsed value is in plausible range.
        is_plausible: Whether text passes plausibility checks.
    """

    line_score: float
    fill_ratio: float
    aspect_ratio: float
    member_count: int
    width: int
    height: int
    has_digit: bool
    has_suffix: bool
    has_decimal: bool
    starts_with_nonzero: bool
    text_length: int
    parsed_value: int | None
    value_in_range: bool
    is_plausible: bool

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    def to_vector(self) -> list[float]:
        """Convert to feature vector for ML model.

        Returns:
            List of numeric features.
        """
        return [
            self.line_score,
            self.fill_ratio,
            self.aspect_ratio,
            float(self.member_count),
            float(self.width),
            float(self.height),
            1.0 if self.has_digit else 0.0,
            1.0 if self.has_suffix else 0.0,
            1.0 if self.has_decimal else 0.0,
            1.0 if self.starts_with_nonzero else 0.0,
            float(self.text_length),
            1.0 if self.parsed_value is not None else 0.0,
            1.0 if self.value_in_range else 0.0,
            1.0 if self.is_plausible else 0.0,
        ]

    @classmethod
    def from_candidate(
        cls,
        line_score: float,
        member_count: int,
        width: int,
        height: int,
        pixel_count: int,
        raw_text: str,
    ) -> ConfidenceFeatures:
        """Create features from OCR candidate.

        Args:
            line_score: Heuristic line score.
            member_count: Number of connected components.
            width: Bounding box width.
            height: Bounding box height.
            pixel_count: Number of text pixels.
            raw_text: Raw OCR text.

        Returns:
            ConfidenceFeatures object.
        """
        area = max(width * height, 1)
        fill_ratio = pixel_count / area
        aspect_ratio = width / max(height, 1)

        parsed_value = _parse_damage_value(raw_text) if raw_text else None

        # Value range check (100 to 100 million)
        value_in_range = False
        if parsed_value is not None:
            value_in_range = 100 <= parsed_value <= 100_000_000

        return cls(
            line_score=line_score,
            fill_ratio=fill_ratio,
            aspect_ratio=aspect_ratio,
            member_count=member_count,
            width=width,
            height=height,
            has_digit=any(c.isdigit() for c in raw_text) if raw_text else False,
            has_suffix=any(c in raw_text.upper() for c in "KMB") if raw_text else False,
            has_decimal="." in raw_text if raw_text else False,
            starts_with_nonzero=(raw_text and raw_text[0].isdigit() and raw_text[0] != '0') if raw_text else False,
            text_length=len(raw_text) if raw_text else 0,
            parsed_value=parsed_value,
            value_in_range=value_in_range,
            is_plausible=_is_plausible_damage_text(raw_text) if raw_text else False,
        )


@dataclass
class ConfidencePrediction:
    """Prediction from confidence classifier.

    Attributes:
        confidence: Predicted confidence score (0.0-1.0).
        probability: Raw probability from classifier.
        decision: Classification decision (hit/no_hit).
        threshold: Threshold used for decision.
        model_version: Version of model used.
    """

    confidence: float
    probability: float
    decision: Literal["hit", "no_hit"]
    threshold: float
    model_version: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "confidence": round(self.confidence, 4),
            "probability": round(self.probability, 4),
            "decision": self.decision,
            "threshold": self.threshold,
            "model_version": self.model_version,
        }


class ConfidenceClassifier:
    """ML-based confidence classifier for detection candidates.

    Uses logistic regression (or similar) to predict whether
    an OCR candidate is a real damage number.

    Example:
        classifier = ConfidenceClassifier()

        # Extract features from candidate
        features = ConfidenceFeatures.from_candidate(
            line_score=8.5,
            member_count=3,
            width=80,
            height=24,
            pixel_count=400,
            raw_text="1234",
        )

        # Get prediction
        prediction = classifier.predict(features)
        print(f"Confidence: {prediction.confidence:.2%}")
        print(f"Decision: {prediction.decision}")
    """

    MODEL_VERSION = "1.0.0"

    def __init__(
        self,
        model_path: Path | str | None = None,
        threshold: float = 0.5,
    ) -> None:
        """Initialize confidence classifier.

        Args:
            model_path: Path to trained model file. Uses default if None.
            threshold: Decision threshold (0.0-1.0).
        """
        self.model_path = Path(model_path) if model_path else None
        self.threshold = threshold
        self.model = None
        self.feature_names = [
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

        # Default weights (heuristic-based initial model)
        self.default_weights = self._create_default_weights()

        # Load model if provided
        if self.model_path and self.model_path.exists():
            self._load_model(self.model_path)

    def _create_default_weights(self) -> dict[str, float]:
        """Create default weights based on heuristic knowledge.

        Returns:
            Dictionary of feature weights.
        """
        return {
            "line_score": 0.15,  # Higher is better
            "fill_ratio": -0.20,  # Lower is better (0.95 is bad)
            "aspect_ratio": 0.05,  # Moderate preference
            "member_count": 0.03,  # Slight preference for multiple components
            "width": -0.001,  # Slight penalty for very wide
            "height": -0.001,  # Slight penalty for very tall
            "has_digit": 0.25,  # Critical - must have digits
            "has_suffix": 0.05,  # Nice to have
            "has_decimal": 0.02,  # Slight positive
            "starts_with_nonzero": 0.05,  # Good sign
            "text_length": -0.02,  # Shorter is better
            "parsed_value": 0.05,  # Good if parseable
            "value_in_range": 0.10,  # Important
            "is_plausible": 0.25,  # Critical - plausibility check
        }

    def predict(self, features: ConfidenceFeatures) -> ConfidencePrediction:
        """Predict confidence for features.

        Args:
            features: Feature vector.

        Returns:
            ConfidencePrediction object.
        """
        # Get probability from model
        if self.model is not None:
            probability = self._predict_with_model(features)
        else:
            probability = self._predict_with_weights(features)

        # Apply sigmoid to get confidence
        confidence = self._sigmoid(probability)

        # Make decision
        decision = "hit" if confidence >= self.threshold else "no_hit"

        return ConfidencePrediction(
            confidence=confidence,
            probability=probability,
            decision=decision,
            threshold=self.threshold,
            model_version=self.MODEL_VERSION,
        )

    def _predict_with_weights(self, features: ConfidenceFeatures) -> float:
        """Predict using default weights.

        Args:
            features: Feature vector.

        Returns:
            Raw score (before sigmoid).
        """
        feature_dict = features.to_dict()
        score = 0.0

        for name, weight in self.default_weights.items():
            value = feature_dict.get(name, 0)
            if isinstance(value, bool):
                value = 1.0 if value else 0.0
            elif value is None:
                value = 0.0
            score += weight * float(value)

        # Normalize score to roughly 0-1 range before sigmoid
        return (score - 0.5) * 4.0

    def _predict_with_model(self, features: ConfidenceFeatures) -> float:
        """Predict using trained model.

        Args:
            features: Feature vector.

        Returns:
            Raw score from model.
        """
        if self.model is None:
            return self._predict_with_weights(features)

        try:
            import numpy as np
            from sklearn.linear_model import LogisticRegression

            if not isinstance(self.model, LogisticRegression):
                return self._predict_with_weights(features)

            vector = np.array([features.to_vector()])
            # Get decision function value (before sigmoid)
            score = self.model.decision_function(vector)[0]
            return float(score)

        except (ImportError, ValueError):
            return self._predict_with_weights(features)

    def _sigmoid(self, x: float) -> float:
        """Sigmoid function.

        Args:
            x: Input value.

        Returns:
            Sigmoid output (0.0-1.0).
        """
        import math
        return 1.0 / (1.0 + math.exp(-x))

    def _load_model(self, model_path: Path) -> None:
        """Load trained model from file.

        Args:
            model_path: Path to model file.
        """
        try:
            import joblib
            self.model = joblib.load(model_path)
        except (ImportError, FileNotFoundError):
            self.model = None

    def save_model(self, model_path: Path | str) -> None:
        """Save model to file.

        Args:
            model_path: Path to save model.
        """
        if self.model is None:
            return

        import joblib
        model_path = Path(model_path)
        model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.model, model_path)

    def train(
        self,
        features: list[ConfidenceFeatures],
        labels: list[int],
        save_path: Path | str | None = None,
    ) -> dict[str, float]:
        """Train classifier on labeled data.

        Args:
            features: List of feature objects.
            labels: List of labels (1=hit, 0=no_hit).
            save_path: Optional path to save trained model.

        Returns:
            Training metrics (accuracy, precision, recall, f1).
        """
        try:
            import numpy as np
            from sklearn.linear_model import LogisticRegression
            from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
        except ImportError:
            return {
                "error": "scikit-learn not installed",
                "accuracy": 0.0,
            }

        # Convert to arrays
        X = np.array([f.to_vector() for f in features])
        y = np.array(labels)

        # Train model
        self.model = LogisticRegression(
            max_iter=1000,
            class_weight="balanced",
            random_state=42,
        )
        self.model.fit(X, y)

        # Evaluate
        predictions = self.model.predict(X)
        metrics = {
            "accuracy": float(accuracy_score(y, predictions)),
            "precision": float(precision_score(y, predictions, zero_division=0)),
            "recall": float(recall_score(y, predictions, zero_division=0)),
            "f1": float(f1_score(y, predictions, zero_division=0)),
        }

        # Save if requested
        if save_path:
            self.save_model(save_path)

        return metrics

    def get_feature_importance(self) -> dict[str, float]:
        """Get feature importance from trained model.

        Returns:
            Dictionary of feature names to importance scores.
        """
        if self.model is None:
            return self.default_weights

        try:
            import numpy as np

            if hasattr(self.model, "coef_"):
                coefs = np.abs(self.model.coef_[0])
                return dict(zip(self.feature_names, coefs.tolist()))
        except (ImportError, IndexError):
            pass

        return self.default_weights


class ConfidenceTrainingData:
    """Helper for creating training data for confidence classifier.

    Example:
        training_data = ConfidenceTrainingData()

        # Add positive examples (real damage numbers)
        training_data.add_hit(
            line_score=8.5,
            member_count=3,
            width=80,
            height=24,
            pixel_count=400,
            raw_text="1234",
        )

        # Add negative examples (false positives)
        training_data.add_miss(
            line_score=3.2,
            member_count=1,
            width=200,
            height=100,
            pixel_count=5000,
            raw_text="UI_ELEMENT",
        )

        # Export for training
        training_data.export("training_data.json")
    """

    def __init__(self) -> None:
        """Initialize training data collector."""
        self.samples: list[tuple[ConfidenceFeatures, int]] = []

    def add_hit(
        self,
        line_score: float,
        member_count: int,
        width: int,
        height: int,
        pixel_count: int,
        raw_text: str,
    ) -> None:
        """Add a positive example (real damage number).

        Args:
            line_score: Heuristic line score.
            member_count: Number of connected components.
            width: Bounding box width.
            height: Bounding box height.
            pixel_count: Number of text pixels.
            raw_text: OCR text.
        """
        features = ConfidenceFeatures.from_candidate(
            line_score=line_score,
            member_count=member_count,
            width=width,
            height=height,
            pixel_count=pixel_count,
            raw_text=raw_text,
        )
        self.samples.append((features, 1))  # Label 1 = hit

    def add_miss(
        self,
        line_score: float,
        member_count: int,
        width: int,
        height: int,
        pixel_count: int,
        raw_text: str,
    ) -> None:
        """Add a negative example (false positive).

        Args:
            line_score: Heuristic line score.
            member_count: Number of connected components.
            width: Bounding box width.
            height: Bounding box height.
            pixel_count: Number of text pixels.
            raw_text: OCR text.
        """
        features = ConfidenceFeatures.from_candidate(
            line_score=line_score,
            member_count=member_count,
            width=width,
            height=height,
            pixel_count=pixel_count,
            raw_text=raw_text,
        )
        self.samples.append((features, 0))  # Label 0 = no_hit

    def add_from_benchmark(
        self,
        benchmark_results: list[dict[str, Any]],
        ground_truth: list[dict[str, Any]],
    ) -> None:
        """Add samples from benchmark results.

        Args:
            benchmark_results: Detection results from benchmark.
            ground_truth: Ground truth annotations.
        """
        # Match detections to ground truth
        for result in benchmark_results:
            matched = self._match_to_ground_truth(result, ground_truth)
            label = 1 if matched else 0

            features = ConfidenceFeatures(
                line_score=result.get("line_score", 5.0),
                fill_ratio=result.get("fill_ratio", 0.3),
                aspect_ratio=result.get("aspect_ratio", 2.0),
                member_count=result.get("member_count", 2),
                width=result.get("width", 80),
                height=result.get("height", 24),
                has_digit=result.get("has_digit", False),
                has_suffix=result.get("has_suffix", False),
                has_decimal=result.get("has_decimal", False),
                starts_with_nonzero=result.get("starts_with_nonzero", True),
                text_length=result.get("text_length", 4),
                parsed_value=result.get("parsed_value"),
                value_in_range=result.get("value_in_range", False),
                is_plausible=result.get("is_plausible", False),
            )
            self.samples.append((features, label))

    def _match_to_ground_truth(
        self,
        result: dict[str, Any],
        ground_truth: list[dict[str, Any]],
    ) -> bool:
        """Check if result matches any ground truth.

        Args:
            result: Detection result.
            ground_truth: Ground truth annotations.

        Returns:
            True if matched.
        """
        result_frame = result.get("frame", 0)
        result_value = result.get("parsed_value", 0)
        result_x = result.get("center_x", 0)
        result_y = result.get("center_y", 0)

        for gt in ground_truth:
            gt_frame = gt.get("frame", 0)
            gt_value = gt.get("value", 0)
            gt_x = gt.get("x", 0)
            gt_y = gt.get("y", 0)

            # Check frame match
            if abs(result_frame - gt_frame) > 3:
                continue

            # Check value match (within 10%)
            if gt_value > 0:
                value_diff = abs(result_value - gt_value) / gt_value
                if value_diff > 0.1:
                    continue

            # Check spatial match (within 70px)
            distance = ((result_x - gt_x) ** 2 + (result_y - gt_y) ** 2) ** 0.5
            if distance > 70:
                continue

            return True

        return False

    def export(self, output_path: Path | str) -> None:
        """Export training data to JSON file.

        Args:
            output_path: Path to output file.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "samples": [
                {
                    "features": f.to_dict(),
                    "label": l,
                }
                for f, l in self.samples
            ],
            "total_samples": len(self.samples),
            "positive_samples": sum(1 for _, l in self.samples if l == 1),
            "negative_samples": sum(1 for _, l in self.samples if l == 0),
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, input_path: Path | str) -> ConfidenceTrainingData:
        """Load training data from JSON file.

        Args:
            input_path: Path to input file.

        Returns:
            ConfidenceTrainingData object.
        """
        input_path = Path(input_path)
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        training_data = cls()
        for sample in data.get("samples", []):
            features_dict = sample.get("features", {})
            label = sample.get("label", 0)

            features = ConfidenceFeatures(**features_dict)
            training_data.samples.append((features, label))

        return training_data

    def get_features_and_labels(self) -> tuple[list[ConfidenceFeatures], list[int]]:
        """Get features and labels as separate lists.

        Returns:
            Tuple of (features, labels).
        """
        features = [f for f, _ in self.samples]
        labels = [l for _, l in self.samples]
        return features, labels

    def get_statistics(self) -> dict[str, Any]:
        """Get training data statistics.

        Returns:
            Dictionary of statistics.
        """
        if not self.samples:
            return {"total": 0, "positive": 0, "negative": 0}

        positive = sum(1 for _, l in self.samples if l == 1)
        negative = len(self.samples) - positive

        return {
            "total": len(self.samples),
            "positive": positive,
            "negative": negative,
            "positive_ratio": positive / len(self.samples) if self.samples else 0,
        }
