@echo off
REM Run the D4V transparent game overlay
REM Shows AVG DMG and LAST DMG in bottom-left of Diablo IV window

echo D4V Game Overlay
echo.
echo Choose mode:
echo   1. Game Overlay Only (standalone)
echo   2. Live Preview + Game Overlay (both windows)
echo.
set /p mode="Enter choice (1 or 2): "

if "%mode%"=="2" (
    echo.
    echo Starting Live Preview with Game Overlay...
    echo.
    uv run d4v live-preview --with-overlay
) else (
    echo.
    echo Starting Game Overlay only...
    echo.
    uv run d4v game-overlay
)
