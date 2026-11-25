# Setup and configuration

Use Windows 10/11 with Python 3.11+ and Microsoft Edge WebView2 for the dashboard.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt .
python app.py --dashboard
```

Select an AI provider in the dashboard. Alternatively, copy `.env.example` to `.env` and configure the appropriate provider key and `AGENT_BRAIN_MODEL`. Local inference needs a separately installed server and model; `OLLAMA_BASE_URL` selects the Ollama endpoint.

Telegram uses `TELEGRAM_BOT_TOKEN` and `TELEGRAM_ALLOWED_CHAT_ID`, or the dashboard's stored settings. Do not commit these values.

Source runs load configuration from the project `.env` and AppData. Frozen builds use a writable `.env` beside the executable when possible, with `%APPDATA%\PRIVACY68` as a fallback. Preferences are stored in `user_profile.json` under that AppData folder.

## Updating from an older installation

Audio settings are no longer read. Existing settings and credentials are preserved. To remove previously installed speech packages from your development environment, create a fresh virtual environment from the current requirements.

Old executables do not change when source files are edited. Rebuild them with:

```powershell
.\build.bat
```

PyInstaller collects dashboard HTML, Markdown skill resources, native services, and channels. It excludes the retired audio engines. Inno Setup packages the Windows installer.
