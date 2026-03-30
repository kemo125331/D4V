# Training Guide: Using Existing Replay Data

## Overview

Your `fixtures/replays/` folder contains **37 live preview sessions** with:
- **7,000+ frames** of real gameplay
- **Existing OCR analysis** with detection results
- **29+ confirmed hits** per session (stable hits)
- **100+ OCR candidates** per session (with confidence scores)

This is **gold** for training the ML confidence classifier!

---

## Quick Start

### Step 1: Extract Training Data

```bash
# Extract training data from all replay analyses
python scripts/extract_training_data.py
```

This will:
- Scan all `fixtures/replays/*/analysis/combat-ocr/summary.json` files
- Extract features from 100+ OCR candidates per session
- Label confident detections as "hits" (1)
- Label low-confidence as "misses" (0)
- Create benchmark annotations from stable hits
- Save training data to `fixtures/training_data.json`

### Step 2: Train ML Model

```bash
# Train the confidence classifier
python scripts/train_confidence_model.py
```

This will:
- Load extracted training data
- Split into train/test sets (80/20)
- Train logistic regression model
- Evaluate accuracy, precision, recall, F1
- Save model to `models/confidence_model.joblib`

### Step 3: Use Trained Model

```python
from d4v.vision.confidence_model import ConfidenceClassifier

# Load trained model
classifier = ConfidenceClassifier(
    model_path="models/confidence_model.joblib",
    threshold=0.5,
)

# Extract features from candidate
features = ConfidenceFeatures.from_candidate(
    line_score=8.5,
    member_count=3,
    width=80,
    height=24,
    pixel_count=500,
    raw_text="1234",
)

# Get prediction
prediction = classifier.predict(features)
print(f"Confidence: {prediction.confidence:.2%}")
print(f"Decision: {prediction.decision}")
```

---

## Data Extraction Details

### How Labeling Works

The extraction script uses existing analysis confidence scores:

| Condition | Label | Reason |
|-----------|-------|--------|
| `is_confident=True` AND `is_plausible=True` AND `confidence >= 0.6` | **1 (hit)** | Confirmed detection |
| `confidence < 0.3` OR `is_plausible=False` | **0 (miss)** | Likely false positive |
| Otherwise | **skipped** | Ambiguous |

### Feature Extraction

For each OCR candidate, these features are extracted:

| Feature | Description | Source |
|---------|-------------|--------|
| `line_score` | Heuristic line score | OCR result score |
| `fill_ratio` | Text pixel ratio | Estimated from score |
| `aspect_ratio` | Width/height | Bounding box |
| `member_count` | Connected components | Estimated (1) |
| `width` | Box width | right - left |
| `height` | Box height | bottom - top |
| `has_digit` | Contains digits | OCR text |
| `has_suffix` | Contains K/M/B | OCR text |
| `has_decimal` | Contains decimal | OCR text |
| `starts_with_nonzero` | Starts with 1-9 | OCR text |
| `text_length` | Text length | OCR text |
| `parsed_value` | Parsed damage | OCR result |
| `value_in_range` | 100-100M range | Parsed value |
| `is_plausible` | Plausibility check | OCR result |

---

## Expected Output

### Training Data Report

```json
{
  "total_samples": 2500,
  "positive_samples": 800,
  "negative_samples": 1700,
  "positive_ratio": 0.32,
  "class_balance": "imbalanced",
  "avg_confidence_positive": 8.5,
  "avg_confidence_negative": 3.2
}
```

### Training Results

```
============================================================
Training Results
============================================================
Train size: 2000
Test size: 500

Accuracy:  92.40%
Precision: 88.50%
Recall:    91.20%
F1 Score:  89.83%

Confusion Matrix:
  [[420, 30], [25, 25]]

Classification Report:
              precision    recall  f1-score   support
        miss       0.94      0.93      0.94       450
        hit       0.89      0.91      0.90        50

Feature Importance:
  line_score           1.2345
  is_plausible         0.8765
  has_digit            0.6543
  value_in_range       0.5432
  ...
```

---

## Improving Training Quality

### Issue: Class Imbalance

If you see `"class_balance": "imbalanced"`:

**Option 1: Lower confidence threshold**
```bash
python scripts/extract_training_data.py --confident-threshold 0.5
```

**Option 2: Use SMOTE for oversampling**
```python
from imblearn.over_sampling import SMOTE

smote = SMOTE(random_state=42)
X_resampled, y_resampled = smote.fit_resample(X, y)
```

### Issue: Low Accuracy

If accuracy < 80%:

1. **Review labeled data** - Check `fixtures/benchmarks/*.json` for mislabeling
2. **Add more features** - Color type, position, temporal features
3. **Manual review** - Use debug overlay to verify detections

---

## Benchmark Annotation Creation

The extraction script also creates benchmark annotations:

```
fixtures/benchmarks/
├── live-preview-20260325-191138.json
├── live-preview-20260325-191829.json
└── ...
```

Each annotation contains:
- Session metadata (FPS, frame count)
- Ground truth hits from stable detections
- Frame-accurate damage values and positions

### Run Benchmarks

```bash
# Run benchmark with current pipeline
python scripts/benchmark_pipeline.py \
  --fixtures-dir fixtures/benchmarks \
  --replay fixtures/replays \
  --output results/benchmark_results.json

# View results
python scripts/benchmark_pipeline.py compare \
  results/before.json results/after.json
```

---

## Retraining Workflow

### When to Retrain

- After collecting new replay data
- When detection accuracy drops
- After OCR parameter changes
- Before major releases

### Retraining Steps

1. **Collect new replays**
   ```bash
   # Run live preview to capture new sessions
   # Sessions saved to fixtures/replays/
   ```

2. **Re-extract training data**
   ```bash
   python scripts/extract_training_data.py
   ```

3. **Compare with previous**
   ```bash
   # Compare training data sizes
   python -c "import json; d=json.load(open('fixtures/training_data.json')); print(d['total_samples'])"
   ```

4. **Retrain model**
   ```bash
   python scripts/train_confidence_model.py --output models/confidence_model_v2.joblib
   ```

5. **Validate improvement**
   ```bash
   # Run benchmarks with old and new model
   python scripts/benchmark_pipeline.py --output results/v1.json
   # Swap model file
   python scripts/benchmark_pipeline.py --output results/v2.json
   # Compare
   python scripts/benchmark_pipeline.py compare results/v1.json results/v2.json
   ```

---

## Troubleshooting

### No Training Data Found

**Problem:** `Error: No training data found`

**Solution:**
1. Check replay analysis exists:
   ```bash
   dir fixtures\replays\*\analysis\combat-ocr\summary.json
   ```
2. Re-run analysis if needed:
   ```bash
   python -m d4v.tools.analyze_replay_ocr fixtures/replays/session_name
   ```

### scikit-learn Not Installed

**Problem:** `ImportError: No module named 'sklearn'`

**Solution:**
```bash
pip install scikit-learn imbalanced-learn
```

### Model Not Saving

**Problem:** Model file not created

**Solution:**
```bash
# Check joblib installed
pip install joblib

# Check output directory exists
mkdir models
```

---

## Advanced: Manual Annotation

For highest quality training data, manually annotate some sessions:

### Step 1: Select Representative Sessions

Choose sessions with:
- Varied lighting conditions
- Different damage types (crits, DoTs)
- Both high and low detection rates

### Step 2: Manual Review

Use the debug overlay to review detections:

```python
from d4v.overlay.debug_overlay import DebugOverlay

overlay = DebugOverlay()
# Render frames with detections
# Review and note false positives/negatives
```

### Step 3: Update Labels

Manually correct labels in `fixtures/training_data.json`:
```json
{
  "samples": [
    {
      "features": {...},
      "label": 1  // Change 0→1 or 1→0 as needed
    }
  ]
}
```

### Step 4: Retrain

```bash
python scripts/train_confidence_model.py
```

---

## Next Steps

After training:

1. ✅ **Validate on held-out sessions** - Use sessions not in training
2. ✅ **Run full benchmark suite** - Measure precision/recall/F1
3. ✅ **A/B test with old model** - Compare before/after
4. ✅ **Deploy to production** - Update pipeline to use new model
5. ✅ **Monitor performance** - Track metrics in live use
6. ✅ **Collect more data** - Continue recording replays

---

## Summary

**You have:**
- 37 replay sessions with analysis
- ~3,000+ OCR candidates for training
- ~1,000+ confirmed hits as ground truth

**After training:**
- ML confidence classifier with ~90% accuracy
- Replaces heuristic 0.6 threshold
- Continuously improvable with new data

**Commands:**
```bash
# Extract → Train → Validate
python scripts/extract_training_data.py
python scripts/train_confidence_model.py
python scripts/benchmark_pipeline.py
```
