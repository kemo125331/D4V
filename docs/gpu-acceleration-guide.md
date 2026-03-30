# GPU Acceleration Guide for D4V Training

## Your Hardware

**GPU:** NVIDIA GeForce RTX 4070 SUPER (12GB VRAM)  
**Driver:** 595.97

## Current Limitations

Python 3.14 is too new for:
- ❌ PyTorch CUDA builds
- ❌ TensorFlow GPU
- ❌ Pillow-SIMD

## What CAN Be GPU-Accelerated

### 1. OpenCV Operations (Available Now)

OpenCV automatically uses CPU optimizations (SSE, AVX) and can use CUDA if installed:

```bash
# Install optimized OpenCV
pip install opencv-contrib-python
```

**GPU-accelerated operations:**
- Image resizing (`cv2.resize`)
- Color space conversion (`cv2.cvtColor`)
- Thresholding (`cv2.threshold`)
- Morphological operations (`cv2.dilate`, `cv2.erode`)
- Connected components (`cv2.connectedComponentsWithStats`)

### 2. Tesseract OCR with CUDA

Tesseract 5+ can use OpenCL for GPU acceleration:

**Install Tesseract with GPU support:**
```bash
# Download from: https://github.com/UB-Mannheim/tesseract/wiki
# Choose version with OpenCL support
```

**Enable GPU in code:**
```python
import pytesseract
pytesseract.run_tesseract("--opencl-device 0")
```

### 3. Batch Processing Optimization

Since full GPU ML training isn't available yet, we optimize with:

1. **Parallel Processing** - Use all CPU cores
2. **Batched Operations** - Process multiple frames together
3. **Memory Mapping** - Avoid loading all frames into RAM
4. **Async I/O** - Overlap disk I/O with processing

---

## Optimized Batch Processing Script

```bash
# Process all sessions with parallelization
python scripts/process_all_replays_parallel.py --workers 8
```

**Expected Speedup:**
- 8 workers: ~8x faster than sequential
- Estimated time: 15-30 minutes for all 32 sessions

---

## Alternative: Use WSL2 with PyTorch

If you need PyTorch GPU training:

1. **Install WSL2** (Windows Subsystem for Linux)
2. **Install Ubuntu** from Microsoft Store
3. **Install PyTorch** in WSL2:
   ```bash
   pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
   ```
4. **Run training** in WSL2 environment

**Benefits:**
- Full GPU acceleration for ML training
- CUDA support
- Better performance for large datasets

---

## Current Best Approach

For your RTX 4070 SUPER, the best immediate optimization is:

```bash
# 1. Install dependencies
pip install opencv-contrib-python

# 2. Run parallel batch processing
python scripts/process_all_replays_parallel.py --workers 8

# 3. Train model (CPU-based, but fast with 30x more data)
python scripts/train_confidence_model.py
```

**Expected Results:**
- Processing: 15-30 minutes (all 32 sessions)
- Training: ~1-2 minutes (11,000+ samples)
- Model accuracy: 99%+ (vs 98.63% currently)

---

## Future: Full GPU Pipeline

When Python 3.14 support improves:

```bash
# Install PyTorch with CUDA
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# Train deep learning model
python scripts/train_deep_confidence_model.py --gpu
```

**Expected improvements:**
- Training time: 30 seconds (vs 2 minutes)
- Can use neural networks (vs logistic regression)
- Potential accuracy: 99.5%+

---

## Summary

**Now:**
- ✅ OpenCV optimized operations
- ✅ Parallel batch processing (8 workers)
- ✅ Fast CPU-based ML training

**Later (WSL2 or Python 3.13):**
- ⏳ Full PyTorch GPU training
- ⏳ Deep learning models
- ⏳ Even faster processing

**Recommendation:** Run parallel batch processing now, retrain with more data. The 30x more samples will improve accuracy more than GPU acceleration would.
