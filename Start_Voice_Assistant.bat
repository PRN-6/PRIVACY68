@echo off
setlocal
cd /d "%~dp0"
title PRIVACY68 Voice Assistant

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found. Run Start_Dashboard.bat first.
    pause
    exit /b 1
)

echo Starting PRIVACY68 Voice Assistant...
.\.venv\Scripts\python.exe app.py
