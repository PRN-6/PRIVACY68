# PRIVACY68 source installer for Windows.
$ErrorActionPreference = "Stop"
$repoUrl = "https://github.com/PRN-6/PRIVACY68.git"
$installDir = Join-Path $HOME "PRIVACY68"

Write-Host "Installing PRIVACY68..." -ForegroundColor Cyan

$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCommand) {
    throw "Python 3.11 or later is required. Install Python, then rerun this command."
}

$pythonVersionText = & $pythonCommand.Source -c "import sys; print('.'.join(map(str, sys.version_info[:3])))"
if ($LASTEXITCODE -ne 0 -or [version]$pythonVersionText -lt [version]"3.11") {
    throw "Python 3.11 or later is required; found Python $pythonVersionText."
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git is required to install PRIVACY68 from source. Install Git for Windows, then rerun this command."
}

if (-not (Test-Path -LiteralPath $installDir)) {
    Write-Host "Cloning the repository into $installDir..." -ForegroundColor Yellow
    & git clone $repoUrl $installDir
    if ($LASTEXITCODE -ne 0) {
        throw "Could not clone the PRIVACY68 repository."
    }
} elseif (-not (Test-Path -LiteralPath (Join-Path $installDir ".git"))) {
    throw "$installDir already exists but is not a Git repository. Move it and rerun this command."
}

Push-Location $installDir
try {
    $venvPython = Join-Path $installDir ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $venvPython)) {
        Write-Host "Creating a Python virtual environment..." -ForegroundColor Yellow
        & $pythonCommand.Source -m venv .venv
        if ($LASTEXITCODE -ne 0) {
            throw "Could not create the virtual environment."
        }
    }

    Write-Host "Installing PRIVACY68 and its dependencies..." -ForegroundColor Yellow
    & $venvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        throw "Could not upgrade pip."
    }
    & $venvPython -m pip install -e .
    if ($LASTEXITCODE -ne 0) {
        throw "Dependency installation failed. Check the pip output above."
    }

    Write-Host ""
    Write-Host "PRIVACY68 was installed in $installDir" -ForegroundColor Green
    Write-Host "Start it with: & `"$venvPython`" `"$installDir\app.py`"" -ForegroundColor Cyan
    Write-Host "The configured Agent Brain model may require a separately installed and configured provider." -ForegroundColor Yellow
    if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
        Write-Host "Ollama was not detected. Install and configure a compatible provider if your setup uses Ollama." -ForegroundColor Yellow
    }
} finally {
    Pop-Location
}
