@echo off
cd /d "%~dp0"
echo Starting D4V Live Preview...
uv run d4v live-preview --live
pause
