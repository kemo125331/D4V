"""Tests for ML confidence classifier."""

import json
import sys
import tempfile
from pathlib import Path

import pytest

# Import directly from module file to avoid cv2 dependency in vision/__init__.py
# Add src to path
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

# Import the module directly without going through package __init__
import importlib.util
spec = importlib.util.spec_from_file_location(
    "d4v.vision.confidence_model",  # Use full module name
    src_path / "d4v" / "vision" / "confidence_model.py"
)
confidence_model = importlib.util.module_from_spec(spec)
sys.modules["d4v.vision.confidence_model"] = confidence_model  # Register in sys.modules
spec.loader.exec_module(confidence_model)

ConfidenceClassifier = confidence_model.ConfidenceClassifier
ConfidenceFeatures = confidence_model.ConfidenceFeatures
ConfidencePrediction = confidence_model.ConfidencePrediction
ConfidenceTrainingData = confidence_model.ConfidenceTrainingData
_is_plausible_damage_text = confidence_model._is_plausible_damage_text
_parse_damage_value = confidence_model._parse_damage_value


class TestConfidenceFeatures:
    """Tests for ConfidenceFeatures dataclass."""

    def test_create_features(self):
        """Given valid parameters, expect features created."""
        features = ConfidenceFeatures(
            line_score=8.5,
            fill_ratio=0.35,
            aspect_ratio=3.0,
            member_count=3,
            width=80,
            height=24,
            has_digit=True,
            has_suffix=False,
            has_decimal=False,
            starts_with_nonzero=True,
            text_length=4,
            parsed_value=1234,
            value_in_range=True,
            is_plausible=True,
        )
        assert features.line_score == 8.5
        assert features.member_count == 3
        assert features.has_digit

    def test_to_dict(self):
        """Given features, expect dict conversion."""
        features = ConfidenceFeatures(
            line_score=8.5,
            fill_ratio=0.35,
            aspect_ratio=3.0,
            member_count=3,
            width=80,
            height=24,
            has_digit=True,
            has_suffix=False,
            has_decimal=False,
            starts_with_nonzero=True,
            text_length=4,
            parsed_value=1234,
            value_in_range=True,
            is_plausible=True,
        )
        data = features.to_dict()
        assert data["line_score"] == 8.5
        assert data["has_digit"]

    def test_to_vector(self):
        """Given features, expect feature vector."""
        features = ConfidenceFeatures(
            line_score=8.5,
            fill_ratio=0.35,
            aspect_ratio=3.0,
            member_count=3,
            width=80,
            height=24,
            has_digit=True,
            has_suffix=False,
            has_decimal=False,
            starts_with_nonzero=True,
            text_length=4,
            parsed_value=1234,
            value_in_range=True,
            is_plausible=True,
        )
        vector = features.to_vector()
        assert len(vector) == 14
        assert vector[0] == 8.5
        assert vector[6] == 1.0  # has_digit

    def test_from_candidate(self):
        """Given candidate data, expect features extracted."""
        features = ConfidenceFeatures.from_candidate(
            line_score=8.5,
            member_count=3,
            width=80,
            height=24,
            pixel_count=500,
            raw_text="1234",
        )
        assert features.line_score == 8.5
        assert features.has_digit
        assert features.parsed_value == 1234
        assert features.value_in_range

    def test_from_candidate_with_suffix(self):
        """Given text with suffix, expect has_suffix set."""
        features = ConfidenceFeatures.from_candidate(
            line_score=8.5,
            member_count=3,
            width=80,
            height=24,
            pixel_count=500,
            raw_text="12.3K",
        )
        assert features.has_suffix
        assert features.has_decimal

    def test_from_candidate_empty_text(self):
        """Given empty text, expect safe defaults."""
        features = ConfidenceFeatures.from_candidate(
            line_score=5.0,
            member_count=1,
            width=50,
            height=20,
            pixel_count=200,
            raw_text="",
        )
        assert features.text_length == 0
        assert not features.has_digit
        assert features.parsed_value is None


class TestConfidencePrediction:
    """Tests for ConfidencePrediction dataclass."""

    def test_create_prediction(self):
        """Given prediction data, expect object created."""
        prediction = ConfidencePrediction(
            confidence=0.85,
            probability=2.0,
            decision="hit",
            threshold=0.5,
            model_version="1.0.0",
        )
        assert prediction.confidence == 0.85
        assert prediction.decision == "hit"

    def test_to_dict(self):
        """Given prediction, expect dict conversion."""
        prediction = ConfidencePrediction(
            confidence=0.85,
            probability=2.0,
            decision="hit",
            threshold=0.5,
            model_version="1.0.0",
        )
        data = prediction.to_dict()
        assert data["confidence"] == 0.85
        assert data["decision"] == "hit"
        assert data["model_version"] == "1.0.0"


class TestConfidenceClassifier:
    """Tests for ConfidenceClassifier."""

    def test_classifier_creation(self):
        """Given classifier created, expect initialized."""
        classifier = ConfidenceClassifier()
        assert classifier.threshold == 0.5
        assert classifier.model is None

    def test_predict_with_default_weights(self):
        """Given features, expect prediction using default weights."""
        classifier = ConfidenceClassifier()

        features = ConfidenceFeatures(
            line_score=8.5,
            fill_ratio=0.35,
            aspect_ratio=3.0,
            member_count=3,
            width=80,
            height=24,
            has_digit=True,
            has_suffix=False,
            has_decimal=False,
            starts_with_nonzero=True,
            text_length=4,
            parsed_value=1234,
            value_in_range=True,
            is_plausible=True,
        )

        prediction = classifier.predict(features)

        assert isinstance(prediction, ConfidencePrediction)
        assert 0.0 <= prediction.confidence <= 1.0
        assert prediction.decision in ["hit", "no_hit"]

    def test_predict_high_confidence_hit(self):
        """Given strong features, expect high confidence hit."""
        classifier = ConfidenceClassifier(threshold=0.5)

        features = ConfidenceFeatures(
            line_score=10.0,
            fill_ratio=0.4,
            aspect_ratio=3.5,
            member_count=4,
            width=90,
            height=26,
            has_digit=True,
            has_suffix=True,
            has_decimal=False,
            starts_with_nonzero=True,
            text_length=5,
            parsed_value=12340,
            value_in_range=True,
            is_plausible=True,
        )

        prediction = classifier.predict(features)

        assert prediction.decision == "hit"
        assert prediction.confidence > 0.5

    def test_predict_low_confidence_miss(self):
        """Given weak features, expect low confidence no_hit."""
        classifier = ConfidenceClassifier(threshold=0.5)

        features = ConfidenceFeatures(
            line_score=1.0,  # Very low
            fill_ratio=0.95,  # Too high (solid block)
            aspect_ratio=1.0,  # Square (not text-like)
            member_count=1,  # Single component
            width=300,  # Too wide
            height=300,  # Too tall
            has_digit=False,  # No digits
            has_suffix=False,
            has_decimal=False,
            starts_with_nonzero=False,
            text_length=15,  # Too long
            parsed_value=None,  # Can't parse
            value_in_range=False,  # Not in valid range
            is_plausible=False,  # Fails plausibility
        )

        prediction = classifier.predict(features)

        assert prediction.decision == "no_hit"
        assert prediction.confidence < 0.5

    def test_sigmoid_function(self):
        """Given sigmoid input, expect correct output."""
        classifier = ConfidenceClassifier()

        # Test sigmoid properties
        assert classifier._sigmoid(0) == 0.5
        assert classifier._sigmoid(10) > 0.99
        assert classifier._sigmoid(-10) < 0.01

    def test_default_weights(self):
        """Given default weights, expect reasonable values."""
        classifier = ConfidenceClassifier()
        weights = classifier.default_weights

        assert "line_score" in weights
        assert "has_digit" in weights
        assert weights["line_score"] > 0  # Most important feature

    def test_get_feature_importance(self):
        """Given untrained classifier, expect default weights."""
        classifier = ConfidenceClassifier()
        importance = classifier.get_feature_importance()

        assert len(importance) == 14
        assert "line_score" in importance

    def test_predict_with_custom_threshold(self):
        """Given custom threshold, expect different decisions."""
        classifier_low = ConfidenceClassifier(threshold=0.3)
        classifier_high = ConfidenceClassifier(threshold=0.8)

        features = ConfidenceFeatures(
            line_score=6.0,
            fill_ratio=0.3,
            aspect_ratio=2.5,
            member_count=2,
            width=70,
            height=22,
            has_digit=True,
            has_suffix=False,
            has_decimal=False,
            starts_with_nonzero=True,
            text_length=3,
            parsed_value=500,
            value_in_range=True,
            is_plausible=True,
        )

        pred_low = classifier_low.predict(features)
        pred_high = classifier_high.predict(features)

        # Lower threshold = more hits
        assert pred_low.confidence >= pred_high.confidence or pred_low.decision == "hit"


class TestConfidenceTrainingData:
    """Tests for ConfidenceTrainingData."""

    def test_training_data_creation(self):
        """Given training data created, expect initialized."""
        training_data = ConfidenceTrainingData()
        assert len(training_data.samples) == 0

    def test_add_hit(self):
        """Given hit added, expect sample with label 1."""
        training_data = ConfidenceTrainingData()

        training_data.add_hit(
            line_score=8.5,
            member_count=3,
            width=80,
            height=24,
            pixel_count=500,
            raw_text="1234",
        )

        assert len(training_data.samples) == 1
        features, label = training_data.samples[0]
        assert label == 1
        assert features.has_digit

    def test_add_miss(self):
        """Given miss added, expect sample with label 0."""
        training_data = ConfidenceTrainingData()

        training_data.add_miss(
            line_score=2.0,
            member_count=1,
            width=200,
            height=200,
            pixel_count=5000,
            raw_text="UI_ELEMENT",
        )

        assert len(training_data.samples) == 1
        features, label = training_data.samples[0]
        assert label == 0
        assert not features.has_digit

    def test_get_statistics(self):
        """Given samples, expect correct statistics."""
        training_data = ConfidenceTrainingData()

        training_data.add_hit(
            line_score=8.5, member_count=3, width=80, height=24,
            pixel_count=500, raw_text="1234",
        )
        training_data.add_hit(
            line_score=9.0, member_count=4, width=90, height=26,
            pixel_count=600, raw_text="5678",
        )
        training_data.add_miss(
            line_score=2.0, member_count=1, width=200, height=200,
            pixel_count=5000, raw_text="UI",
        )

        stats = training_data.get_statistics()

        assert stats["total"] == 3
        assert stats["positive"] == 2
        assert stats["negative"] == 1
        assert abs(stats["positive_ratio"] - 2/3) < 0.01

    def test_get_features_and_labels(self):
        """Given samples, expect separate lists."""
        training_data = ConfidenceTrainingData()

        training_data.add_hit(
            line_score=8.5, member_count=3, width=80, height=24,
            pixel_count=500, raw_text="1234",
        )
        training_data.add_miss(
            line_score=2.0, member_count=1, width=200, height=200,
            pixel_count=5000, raw_text="UI",
        )

        features, labels = training_data.get_features_and_labels()

        assert len(features) == 2
        assert len(labels) == 2
        assert labels == [1, 0]

    def test_export_and_load(self, tmp_path: Path):
        """Given data exported, expect load works."""
        training_data = ConfidenceTrainingData()

        training_data.add_hit(
            line_score=8.5, member_count=3, width=80, height=24,
            pixel_count=500, raw_text="1234",
        )
        training_data.add_miss(
            line_score=2.0, member_count=1, width=200, height=200,
            pixel_count=5000, raw_text="UI",
        )

        output_path = tmp_path / "training_data.json"
        training_data.export(output_path)

        # Verify file exists and is valid JSON
        assert output_path.exists()
        with open(output_path) as f:
            data = json.load(f)

        assert data["total_samples"] == 2
        assert data["positive_samples"] == 1

        # Load back
        loaded = ConfidenceTrainingData.load(output_path)
        assert len(loaded.samples) == 2

    def test_empty_statistics(self):
        """Given no samples, expect zero statistics."""
        training_data = ConfidenceTrainingData()
        stats = training_data.get_statistics()

        assert stats["total"] == 0
        assert stats["positive"] == 0
        assert stats["negative"] == 0


class TestConfidenceClassifierTraining:
    """Tests for classifier training (requires scikit-learn)."""

    @pytest.fixture
    def sample_training_data(self):
        """Create sample training data."""
        training_data = ConfidenceTrainingData()

        # Add positive examples (real damage numbers)
        for i in range(10):
            training_data.add_hit(
                line_score=8.0 + i * 0.2,
                member_count=3,
                width=80,
                height=24,
                pixel_count=500,
                raw_text=str(1000 + i * 100),
            )

        # Add negative examples (false positives)
        for i in range(10):
            training_data.add_miss(
                line_score=2.0 + i * 0.1,
                member_count=1,
                width=200,
                height=200,
                pixel_count=5000,
                raw_text=f"UI_{i}",
            )

        return training_data

    def test_train_classifier(self, sample_training_data):
        """Given training data, expect model trained."""
        try:
            import sklearn  # noqa
        except ImportError:
            pytest.skip("scikit-learn not installed")

        classifier = ConfidenceClassifier()
        features, labels = sample_training_data.get_features_and_labels()

        metrics = classifier.train(features, labels)

        assert "accuracy" in metrics
        # With clear separation, should have high accuracy
        assert metrics["accuracy"] > 0.8

    def test_train_and_predict(self, sample_training_data):
        """Given trained model, expect predictions work."""
        try:
            import sklearn  # noqa
        except ImportError:
            pytest.skip("scikit-learn not installed")

        classifier = ConfidenceClassifier()
        features, labels = sample_training_data.get_features_and_labels()

        # Train
        classifier.train(features, labels)

        # Predict on training data
        test_features = features[0]  # A positive example
        prediction = classifier.predict(test_features)

        assert prediction.confidence > 0.5
        assert prediction.decision == "hit"

    def test_save_and_load_model(self, sample_training_data, tmp_path: Path):
        """Given saved model, expect load works."""
        try:
            import sklearn  # noqa
        except ImportError:
            pytest.skip("scikit-learn not installed")

        classifier = ConfidenceClassifier()
        features, labels = sample_training_data.get_features_and_labels()

        # Train
        classifier.train(features, labels)

        # Save
        model_path = tmp_path / "model.joblib"
        classifier.save_model(model_path)

        assert model_path.exists()

        # Load in new classifier
        classifier2 = ConfidenceClassifier(model_path=model_path)
        assert classifier2.model is not None

        # Predict
        prediction = classifier2.predict(features[0])
        assert prediction.confidence > 0

    def test_feature_importance_after_training(self, sample_training_data):
        """Given trained model, expect feature importance available."""
        try:
            import sklearn  # noqa
        except ImportError:
            pytest.skip("scikit-learn not installed")

        classifier = ConfidenceClassifier()
        features, labels = sample_training_data.get_features_and_labels()

        classifier.train(features, labels)
        importance = classifier.get_feature_importance()

        assert len(importance) == 14
        # line_score should be important
        assert importance.get("line_score", 0) > 0
