@echo off
cd /d "%~dp0.."
uv run python scripts/live_debug_session.py
pause
