@echo off
setlocal
cd /d "%~dp0"
title PRIVACY68 Control Center

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo ========================================================
    echo  First-time Setup: Creating virtual environment...
    echo ========================================================
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Python not found. Please install Python 3.11 or later from python.org
        pause
        exit /b 1
    )
    echo Installing required packages...
    .\.venv\Scripts\python.exe -m pip install --upgrade pip
    .\.venv\Scripts\python.exe -m pip install -e .
)

start "" ".\.venv\Scripts\pythonw.exe" app.py --dashboard
if errorlevel 1 (
    .\.venv\Scripts\python.exe app.py --dashboard
)
