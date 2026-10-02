@echo off
setlocal enabledelayedexpansion

title CNAT NOISERELIEF - Environment Setup ^& Dependencies
color 0B

echo ===============================================================================
echo                CNAT NOISERELIEF - ENVIRONMENT SETUP
echo             Audio ^& Video Background Noise Reduction Software
echo           Created by Coder ^& AccoTax ^| www.codernaccotax.co.in
echo ===============================================================================
echo.

:: 1. Check Python installation
echo [1/5] Checking Python installation...
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed or not added to your system PATH!
    echo Please install Python 3.10 or newer from https://www.python.org/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYTHON_VER=%%i
echo   -- Found %PYTHON_VER%
echo.

:: 2. Setup / Verify Virtual Environment (.venv)
echo [2/5] Configuring Python Virtual Environment (.venv)...
if not exist ".venv\Scripts\activate.bat" (
    echo   -- Creating new virtual environment at .venv...
    python -m venv .venv
    if %ERRORLEVEL% NEQ 0 (
        echo [WARNING] Could not create .venv. Proceeding with global Python environment.
    ) else (
        echo   -- Virtual environment created successfully.
    )
) else (
    echo   -- Existing virtual environment found at .venv.
)

:: Activate venv if available
if exist ".venv\Scripts\activate.bat" (
    echo   -- Activating virtual environment...
    call .venv\Scripts\activate.bat
    set "PY_CMD=python"
) else (
    set "PY_CMD=python"
)
echo.

:: 3. Upgrade pip and build tools
echo [3/5] Upgrading pip and package managers...
%PY_CMD% -m pip install --upgrade pip setuptools wheel --quiet
echo   -- Package tools up-to-date.
echo.

:: 4. Install / Update project dependencies
echo [4/5] Installing dependencies from requirements.txt...
%PY_CMD% -m pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Failed to install one or more dependencies!
    echo Please check your internet connection or Python version.
    echo.
    pause
    exit /b 1
)
echo   -- All dependencies installed and verified successfully.
echo.

:: 5. Validate FFmpeg and Generate Sample Media
echo [5/5] Checking FFmpeg audio/video engine and test samples...
%PY_CMD% -c "from src.utils.ffmpeg_helper import FFmpegHelper; path=FFmpegHelper.get_ffmpeg_path(); print('  -- FFmpeg engine ready at: ' + (path if path else 'Bundled fallback'))" 2>nul

if not exist "samples\noisy_podcast_fan.wav" (
    echo   -- Generating synthetic audio/video test samples in samples/ ...
    %PY_CMD% scripts\generate_samples.py >nul 2>&1
    if exist "samples\noisy_podcast_fan.wav" (
        echo   -- Test samples generated successfully.
    )
) else (
    echo   -- Test samples already present in samples/ directory.
)
echo.

echo ===============================================================================
echo [SUCCESS] CNAT NOISERELIEF setup completed successfully!
echo ===============================================================================
echo.
echo You can now launch the application at any time by running:
echo     run.bat
echo.

set /p LAUNCH_CHOICE="Would you like to launch CNAT NOISERELIEF now? (Y/N) [default: Y]: "
if /i "%LAUNCH_CHOICE%"=="" set LAUNCH_CHOICE=Y
if /i "%LAUNCH_CHOICE%"=="Y" (
    echo.
    echo Starting CNAT NOISERELIEF...
    start "" run.bat
)

exit /b 0
