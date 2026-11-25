# PRIVACY68

A Windows desktop automation assistant controlled through typed commands. Use the Control Center, the system tray's Quick Command Bar, or the optional Telegram text gateway.

## What it does

- Opens common apps, websites, and searches through deterministic command handlers.
- Routes more complex tasks to the configured cloud or local AI provider.
- Loads Markdown skills from `skills/` and the user's AppData skills folder.
- Checks generated Python with a security guard before running it in a subprocess.
- Provides Gmail browser automation, Windows system controls, and optional Telegram screenshots and text commands.

The application has no speech recognition, microphone capture, wake words, voice enrollment, or spoken responses. Telegram audio attachments are rejected without downloading them. Whisper and speech libraries are no longer required.

## Run from source

Requirements: Windows 10/11, Python 3.11+, and Microsoft Edge WebView2 for the dashboard.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt .
python app.py
```

Double-click the tray icon or select **Run Command** to open the text bar. Press Enter to run a command and Escape to hide it. Open the dashboard directly with:

```powershell
python app.py --dashboard
```

Configure an AI provider in the dashboard or copy `.env.example` to `.env` and supply your settings. Simple app and browser commands do not require an AI key. Complex tasks need a reachable model provider; local inference requires a separately installed model server and model.

Examples: `open chrome`, `open notepad`, `search for Python dataclasses`, `open youtube in brave`.

## Telegram

Configure a bot token and start the gateway from the dashboard. Find the pairing PIN there, then send `/pair <PIN>` to your bot. Once paired, send text instructions, `/status`, `/screenshot`, or `/unpair`. Only the configured chat is authorized. Message edits do not re-execute commands.

## Privacy and execution

Cloud AI requests and Telegram commands use external services. Local model configuration determines where AI processing occurs. Generated scripts run with the current user's permissions; the security guard is not an operating-system sandbox. Review [SECURITY.md](SECURITY.md) before enabling remote control.

Existing `.env` settings and user profiles are preserved. Legacy audio settings are unused. An existing virtual environment may still contain old speech packages; create a fresh environment to get the reduced dependency set. Existing executables must be rebuilt to include these changes.

## Development and packaging

```powershell
python -m unittest discover tests -v
python -m compileall -q actions channels computer_use services skills ui utils tests app.py config.py
.\build.bat
```

The build uses PyInstaller and Inno Setup. See [Contributing](CONTRIBUTING.md), [architecture](doc/ARCHITECTURE.md), and [setup](doc/SETUP_AND_CONFIGURATION.md). Research papers and generated project reports in `docs/` describe earlier versions and are not the current runtime specification.
