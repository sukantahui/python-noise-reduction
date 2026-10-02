@echo off
title CNAT NOISERELIEF - Audio & Video Noise Reduction
echo Starting CNAT NOISERELIEF...
python src\main.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Application exited with error code %ERRORLEVEL%.
    pause
)
