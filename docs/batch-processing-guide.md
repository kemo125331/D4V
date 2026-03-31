# Batch Processing Guide - Remaining 30 Sessions

## Current Status

✅ **7 sessions processed** - 362 training samples, 98.63% accuracy  
⏳ **33 sessions remaining** - Potential ~1,500+ more samples

## Sessions to Process

### Need OCR Analysis First (32 sessions):

```
first-round
live-preview-20260325-193016
live-preview-20260325-193510
live-preview-20260325-193657
live-preview-20260325-193928
live-preview-20260325-205752
live-preview-20260325-211200
live-preview-20260325-212924
live-preview-20260325-213356
live-preview-20260325-214224
live-preview-20260325-214522
live-preview-20260325-214911
live-preview-20260325-215529
live-preview-20260325-215904
live-preview-20260325-220443
live-preview-20260325-220822
live-preview-20260328-204728
live-preview-20260328-205940
live-preview-20260328-223910
live-preview-20260328-224215
live-preview-20260328-224414
live-preview-20260328-224741
live-preview-20260328-224747
live-preview-20260328-225252
live-preview-20260328-225648
live-preview-20260328-230412
live-preview-20260328-231616
live-preview-20260328-232545
live-preview-20260328-233336
live-preview-20260328-235251
live-preview-20260329-004942
_merged
```

## Option 1: Automated Processing (Recommended)

### Step 1: Install Dependencies

```bash
uv sync
```

### Step 2: Run Batch Processing

```bash
python scripts/process_all_replays.py
```

This will:
1. Check which sessions need OCR analysis
2. Run OCR analysis on each session
3. Extract training data from all sessions
4. Retrain the ML model

**Estimated Time:** ~10-20 minutes for all sessions

---

## Option 2: Manual Processing (Session by Session)

### Process One Session

```bash
# Run OCR analysis
python -m d4v.tools.analyze_replay_ocr fixtures/replays/live-preview-20260325-193016

# Verify analysis was created
dir fixtures\replays\live-preview-20260325-193016\analysis\combat-ocr
```

### Repeat for All Sessions

```bash
# Loop through all sessions (PowerShell)
Get-ChildItem fixtures\replays -Directory | ForEach-Object {
    if (!(Test-Path "$($_.FullName)\analysis\combat-ocr\summary.json")) {
        Write-Host "Processing $($_.Name)..."
        python -m d4v.tools.analyze_replay_ocr $_.FullName
    }
}
```

---

## Option 3: Quick Estimate (No OCR)

If you want to estimate potential training data without running OCR:

```bash
python scripts/estimate_training_potential.py
```

This counts frames in each session and estimates sample counts.

---

## Expected Results

Based on current 7 sessions:

| Metric | Current | Projected (40 sessions) |
|--------|---------|------------------------|
| Sessions | 7 | 40 |
| Training Samples | 362 | ~2,000+ |
| Positive (Hits) | 134 | ~750+ |
| Model Accuracy | 98.6% | 99%+ |
| Precision | 96.4% | 98%+ |
| Recall | 100% | 100% |

**Benefits of More Data:**
- Better generalization to edge cases
- More robust to varied lighting/conditions
- Better feature learning
- Lower overfitting risk

---

## After Processing

### Retrain Model

```bash
python scripts/train_confidence_model.py --output models/confidence_model_v2.joblib
```

### Compare Models

```bash
# Benchmark with v1
python scripts/benchmark_pipeline.py --output results/v1.json

# Switch to v2
copy /Y models\confidence_model_v2.joblib models\confidence_model.joblib

# Benchmark with v2
python scripts/benchmark_pipeline.py --output results/v2.json

# Compare
python scripts/benchmark_pipeline.py compare results/v1.json results/v2.json
```

---

## Troubleshooting

### OpenCV Not Available

**Error:** `ModuleNotFoundError: No module named 'cv2'`

**Solution:**
```bash
pip install opencv-python
```

### Session Has No Frames

**Error:** `No frame images found`

**Solution:**
- Check session has PNG files: `dir fixtures\replays\session-name\frames\*.png`
- If empty, session capture failed - skip it

---

## Quick Status Check

```bash
# Check how many sessions have analysis
python -c "from pathlib import Path; print(len(list(Path('fixtures/replays').glob('*/analysis/combat-ocr/summary.json'))))"
```

---

## Recommended Workflow

1. **Run batch processing overnight**
   ```bash
   python scripts/process_all_replays.py
   ```

2. **Next morning: Check results**
   ```bash
   # Should show ~40 sessions processed
   python -c "from pathlib import Path; print(len(list(Path('fixtures/replays').glob('*/analysis/combat-ocr/summary.json'))))"
   ```

3. **Retrain with all data**
   ```bash
   python scripts/extract_training_data_simple.py
   python scripts/train_confidence_model.py --output models/confidence_model_final.joblib
   ```

4. **Validate improvement**
   ```bash
   python scripts/benchmark_pipeline.py
   ```

---

## Summary

**Current:** 7 sessions → 362 samples → 98.63% accuracy  
**Potential:** 40 sessions → ~2,000 samples → 99%+ accuracy

**Command to process all:**
```bash
python scripts/process_all_replays.py
```

**Estimated time:** 10-20 minutes (can run in background)
