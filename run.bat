@echo off
title CNAT NOISERELIEF - Audio & Video Noise Reduction
echo Starting CNAT NOISERELIEF...

if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe src\main.py
) else (
    python src\main.py
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Application exited with error code %ERRORLEVEL%.
    pause
)
