@echo off
setlocal
title PRIVACY68 Windows Installer Build

echo.
echo =====================================================
echo       PRIVACY68  v1.4.2  -  Windows Installer Build
echo =====================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Project virtual environment not found.
    echo Create it with: python -m venv .venv
    echo Then install dependencies with: .venv\Scripts\python.exe -m pip install -e .
    exit /b 1
)

echo [1/2] Building PRIVACY68 application bundle...
echo.
.\.venv\Scripts\python.exe build_exe.py
if errorlevel 1 exit /b 1

echo.
echo [2/2] Looking for Inno Setup 6 compiler...
echo.

set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
    echo [ERROR] Inno Setup 6 was not found.
    echo Install Inno Setup 6 from https://jrsoftware.org/isdl.php
    exit /b 1
)

"%ISCC%" installer.iss
if errorlevel 1 exit /b 1

echo.
echo =====================================================
echo  [DONE] PRIVACY68 installer build complete.
echo.
echo  App bundle : dist\PRIVACY68\
echo  Installer  : installer\PRIVACY68-Setup-v1.4.2.exe
echo =====================================================
echo.
