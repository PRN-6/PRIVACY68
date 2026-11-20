@echo off
setlocal
title PRIVACY68 Official Website Server

echo.
echo =====================================================
echo       PRIVACY68 Official Website Local Server
echo =====================================================
echo.

set "PORT=8080"

:: Check for virtual environment python first, then system python
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

:: Verify website directory exists
if not exist "website\index.html" (
    echo [ERROR] Website directory or index.html not found!
    pause
    exit /b 1
)

echo [INFO] Serving files from: %CD%\website
echo [INFO] Local URL: http://localhost:%PORT%
echo [INFO] Opening default browser...
echo.
echo Press Ctrl+C in this window anytime to stop the server.
echo =====================================================
echo.

:: Open default browser after a 1-second delay
start "" cmd /c "timeout /t 1 /nobreak >nul & start http://localhost:%PORT%"

:: Run Python HTTP server serving the website folder
"%PYTHON_EXE%" -m http.server %PORT% --directory website

if errorlevel 1 (
    echo.
    echo [WARNING] Port %PORT% might be in use, falling back to port 8000...
    start "" cmd /c "timeout /t 1 /nobreak >nul & start http://localhost:8000"
    "%PYTHON_EXE%" -m http.server 8000 --directory website
)

pause
