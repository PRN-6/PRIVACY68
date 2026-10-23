# PRIVACY68 Installation Script for Windows
Write-Host "--------------------------------------------------" -ForegroundColor Cyan
Write-Host "🚀 Installing PRIVACY68 Voice Assistant..." -ForegroundColor Cyan
Write-Host "--------------------------------------------------" -ForegroundColor Cyan

# 1. Check for Python
if (!(Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Python not found. Please install Python 3.11+ first." -ForegroundColor Red
    exit
}

# 2. Setup Directory
$installDir = "$HOME\PRIVACY68"
if (!(Test-Path $installDir)) {
    Write-Host "📂 Cloning repository to $installDir..." -ForegroundColor Yellow
    git clone https://github.com/YOUR_USERNAME/PRIVACY68.git $installDir
}
Set-Location $installDir

# 3. Create Virtual Environment
Write-Host "📦 Creating Virtual Environment..." -ForegroundColor Yellow
python -m venv .venv
& .\.venv\Scripts\Activate.ps1

# 4. Install Dependencies
Write-Host "📥 Installing Dependencies (this may take a few minutes)..." -ForegroundColor Yellow
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .

# 5. Ollama Check
if (!(Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "⚠️ Ollama not found. Downloading Ollama..." -ForegroundColor Magenta
    Invoke-WebRequest -Uri "https://ollama.com/download/OllamaSetup.exe" -OutFile "OllamaSetup.exe"
    Start-Process "OllamaSetup.exe" -Wait
    Remove-Item "OllamaSetup.exe"
}

Write-Host "--------------------------------------------------" -ForegroundColor Cyan
Write-Host "✅ INSTALLATION COMPLETE!" -ForegroundColor Green
Write-Host "👉 You can now start the assistant by typing: privacy68" -ForegroundColor Cyan
Write-Host "--------------------------------------------------" -ForegroundColor Cyan
