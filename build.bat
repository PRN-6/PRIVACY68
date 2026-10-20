@echo off
setlocal EnableDelayedExpansion
title PRIVACY68 v1.4.0 Release Build Pipeline

echo.
echo =====================================================
echo       PRIVACY68  v1.4.0  -  Release Build Pipeline
echo =====================================================
echo.

REM ─── Step 1: Sync website plugin downloads ───────────────────────────────────
echo [1/3] Syncing website plugin downloads...
echo.
.\.venv\Scripts\python.exe sync_website_plugins.py
if %ERRORLEVEL% NEq 0 (
    echo.
    echo [ERROR] Website plugin sync failed! Check output above.
    pause
    exit /b 1
)
echo.

REM ─── Step 2: Build EXE with PyInstaller ─────────────────────────────────────
echo [2/3] Compiling PRIVACY68.exe with PyInstaller...
echo.
.\.venv\Scripts\python.exe build_exe.py %*
if %ERRORLEVEL% NEq 0 (
    echo.
    echo [ERROR] PyInstaller build failed! Check output above.
    pause
    exit /b 1
)

echo.
echo [2/3] EXE build complete: dist\PRIVACY68\PRIVACY68.exe
echo.

REM ─── Step 3: Compile Installer with Inno Setup (optional) ───────────────────
echo [3/3] Looking for Inno Setup Compiler (ISCC.exe)...

set ISCC=""
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
) else if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    set ISCC="C:\Program Files\Inno Setup 6\ISCC.exe"
)

if !ISCC!=="" (
    echo [SKIP] Inno Setup not found — skipping installer creation.
    echo        To create the installer, install Inno Setup 6 from:
    echo        https://jrsoftware.org/isdl.php
) else (
    echo [3/3] Compiling installer with Inno Setup...
    !ISCC! installer.iss
    if %ERRORLEVEL% NEq 0 (
        echo.
        echo [ERROR] Inno Setup compilation failed!
        pause
        exit /b 1
    )
    echo.
    echo [3/3] Installer created: installer\PRIVACY68-Setup-v1.4.0.exe
)

echo.
echo =====================================================
echo  [DONE] PRIVACY68 v1.4.0 Release Build Complete!
echo.
echo  EXE output : dist\PRIVACY68\
echo  Installer  : installer\PRIVACY68-Setup-v1.4.0.exe
echo =====================================================
echo.
pause
