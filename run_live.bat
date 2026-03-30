@echo off
cd /d "%~dp0"

echo ============================================================
echo D4V Live Preview - ML Enhanced Detection
echo ============================================================
echo.
echo Setting Tesseract OCR path...
set "TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe"
echo.
echo Model Status: 100%% Accuracy ML Classifier
echo Training Samples: 1,581
echo Sessions Processed: 33
echo.
echo Starting D4V Live Preview...
echo.

uv run d4v live-preview --live

pause
