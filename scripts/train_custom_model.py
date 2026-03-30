#!/usr/bin/env python3
"""Train an improved ML model with collected data.

Combines existing training data with newly collected data
and trains a better model with feature engineering.

Usage:
    python scripts/train_custom_model.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def load_all_training_data() -> tuple[list, list]:
    """Load training data from all sources."""
    print("=" * 60)
    print("Loading Training Data")
    print("=" * 60)
    
    all_features = []
    all_labels = []
    
    # Load original training data
    original_path = Path("fixtures/training_data.json")
    if original_path.exists():
        print("\n1. Loading original training data...")
        with open(original_path) as f:
            data = json.load(f)
        
        for sample in data.get("samples", []):
            all_features.append(sample["features"])
            all_labels.append(sample["label"])
        
        print(f"   ✓ Loaded {len(data['samples'])} samples")
    
    # Load collected data
    collected_dir = Path("fixtures/training_data_collected")
    if collected_dir.exists():
        print("\n2. Loading collected gameplay data...")
        summary_path = collected_dir / "collection_summary.json"
        
        if summary_path.exists():
            with open(summary_path) as f:
                collected = json.load(f)
            
            # Convert collected samples to features
            for sample in collected.get("samples", []):
                # Create features from detected hits
                features = create_features_from_hit(sample)
                all_features.append(features)
                all_labels.append(1)  # All collected hits are positive
            
            print(f"   ✓ Loaded {len(collected['samples'])} collected samples")
    
    # Generate negative samples (synthetic)
    print("\n3. Generating negative samples...")
    negative_samples = generate_negative_samples(len(all_features) // 3)
    all_features.extend(negative_samples)
    all_labels.extend([0] * len(negative_samples))
    print(f"   ✓ Generated {len(negative_samples)} negative samples")
    
    print(f"\nTotal: {len(all_features)} samples")
    print(f"  Positive: {sum(all_labels)}")
    print(f"  Negative: {len(all_labels) - sum(all_labels)}")
    
    return all_features, all_labels


def create_features_from_hit(hit: dict) -> dict:
    """Create feature dict from a detected hit."""
    text = hit.get("text", "")
    value = hit.get("value", 0)
    confidence = hit.get("confidence", 0.5)
    
    return {
        "line_score": confidence * 12,  # Approximate
        "fill_ratio": 0.35,  # Average
        "aspect_ratio": 3.0,  # Average
        "member_count": 3,  # Average
        "width": 80,  # Average
        "height": 24,  # Average
        "has_digit": any(c.isdigit() for c in text),
        "has_suffix": any(c in text.upper() for c in "KMB"),
        "has_decimal": "." in text,
        "starts_with_nonzero": text and text[0].isdigit() and text[0] != '0',
        "text_length": len(text),
        "parsed_value": value,
        "value_in_range": 100 <= value <= 100_000_000 if value else False,
        "is_plausible": True,  # All collected hits are plausible
    }


def generate_negative_samples(count: int) -> list[dict]:
    """Generate synthetic negative samples."""
    import random
    
    negatives = []
    for _ in range(count):
        # Generate random non-damage-like features
        negatives.append({
            "line_score": random.uniform(2.0, 6.0),
            "fill_ratio": random.uniform(0.5, 0.9),
            "aspect_ratio": random.uniform(0.8, 1.5),
            "member_count": random.randint(1, 2),
            "width": random.randint(100, 300),
            "height": random.randint(100, 300),
            "has_digit": random.choice([True, False]),
            "has_suffix": False,
            "has_decimal": False,
            "starts_with_nonzero": False,
            "text_length": random.randint(5, 15),
            "parsed_value": None,
            "value_in_range": False,
            "is_plausible": False,
        })
    
    return negatives


def train_improved_model(features: list, labels: list):
    """Train an improved model with better feature engineering."""
    try:
        import numpy as np
        from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import train_test_split, cross_val_score
        from sklearn.preprocessing import StandardScaler
        from sklearn.metrics import classification_report, confusion_matrix
    except ImportError:
        print("\n❌ scikit-learn not installed")
        print("Install: pip install scikit-learn")
        return
    
    print("\n" + "=" * 60)
    print("Training Improved Model")
    print("=" * 60)
    
    # Convert to arrays
    feature_names = list(features[0].keys())
    X = np.array([[f.get(name, 0) or 0 for name in feature_names] for f in features])
    y = np.array(labels)
    
    # Handle None and boolean values
    X = np.nan_to_num(X, nan=0.0)
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    print(f"\nTraining set: {len(y_train)} samples")
    print(f"Test set: {len(y_test)} samples")
    
    # Try multiple models
    models = {
        "Logistic Regression": LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42),
        "Random Forest": RandomForestClassifier(n_estimators=100, class_weight="balanced", random_state=42),
        "Gradient Boosting": GradientBoostingClassifier(n_estimators=100, random_state=42),
    }
    
    best_model = None
    best_score = 0
    best_name = ""
    
    for name, model in models.items():
        print(f"\nTraining {name}...")
        
        # Cross-validation
        cv_scores = cross_val_score(model, X_train_scaled, y_train, cv=5, scoring="f1")
        print(f"  CV F1 Score: {cv_scores.mean():.4f} (+/- {cv_scores.std() * 2:.4f})")
        
        # Train and evaluate
        model.fit(X_train_scaled, y_train)
        y_pred = model.predict(X_test_scaled)
        
        from sklearn.metrics import f1_score
        f1 = f1_score(y_test, y_pred)
        print(f"  Test F1 Score: {f1:.4f}")
        
        if f1 > best_score:
            best_score = f1
            best_model = model
            best_name = name
    
    print(f"\n{'=' * 60}")
    print(f"Best Model: {best_name}")
    print(f"Test F1 Score: {best_score:.4f}")
    print(f"{'=' * 60}")
    
    # Final evaluation
    y_pred = best_model.predict(X_test_scaled)
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=["Miss", "Hit"]))
    
    print("\nConfusion Matrix:")
    print(confusion_matrix(y_test, y_pred))
    
    # Feature importance
    if hasattr(best_model, "feature_importances_"):
        importances = best_model.feature_importances_
    elif hasattr(best_model, "coef_"):
        importances = np.abs(best_model.coef_[0])
    else:
        importances = None
    
    if importances is not None:
        print("\nTop 10 Feature Importances:")
        sorted_idx = np.argsort(importances)[::-1][:10]
        for idx in sorted_idx:
            print(f"  {feature_names[idx]:25} {importances[idx]:.4f}")
    
    # Save model
    import joblib
    output_path = Path("models/confidence_model_custom.joblib")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    package = {
        "model": best_model,
        "scaler": scaler,
        "feature_names": feature_names,
    }
    joblib.dump(package, output_path)
    
    print(f"\n✓ Model saved to: {output_path}")
    print("\nTo use this model:")
    print("  copy models\\confidence_model_custom.joblib models\\confidence_model.joblib")
    print("  Then restart: run_live.bat")


def main():
    features, labels = load_all_training_data()
    
    if not features:
        print("\n❌ No training data found!")
        print("\nCollect data first:")
        print("  python scripts/collect_training_data.py")
        return
    
    train_improved_model(features, labels)


if __name__ == "__main__":
    main()
