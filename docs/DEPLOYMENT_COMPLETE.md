# D4V Windows Deployment Complete

## Summary

**Date:** 2026-03-30  
**Status:** Qt-first standalone Windows build

## Delivered

- `models/confidence_model.joblib` for ML scoring
- `src/d4v/vision/pipeline.py` for ML-backed detection
- `src/d4v/ui/shell.py` for the compact Qt desktop shell
- `src/d4v/ui/overlay.py` for the transparent Qt overlay
- `scripts/build_windows.ps1` for local one-file builds
- `.github/workflows/build-windows.yml` for CI artifact builds

## How To Launch

### Normal Use

1. Double-click `dist/D4V.exe`
2. The Qt desktop shell opens
3. Click `Start`

### Source Run

```powershell
uv run d4v-desktop
```

## Build Output

- `dist/D4V.exe`
- `D4V-windows-x64.zip` from GitHub Actions

## Validation

Run both checks before tagging a release:

```powershell
uv run pytest -q tests/ui tests/overlay tests/test_desktop.py tests/tools/test_capture_round.py tests/test_smoke.py
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1
```
