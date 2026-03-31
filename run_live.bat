@echo off
cd /d "%~dp0"

echo ============================================================
echo D4V Live Preview - ML Enhanced Detection
echo ============================================================
echo.
echo OCR Engine: WinOCR
echo.
echo Model Status: 100%% Accuracy ML Classifier
echo Training Samples: 1,581
echo Sessions Processed: 33
echo.
echo Starting D4V Live Preview with Game Overlay...
echo.
echo - Preview Window: Shows ML status and hit log
echo - Game Overlay: Shows AVG DMG and LAST DMG in-game
echo.

uv run d4v live-preview --with-overlay

pause
