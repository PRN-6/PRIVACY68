# Verification

Run the suite on Windows from the repository root:

```powershell
python -m unittest discover tests -v
python -m compileall -q actions channels computer_use services skills ui utils tests app.py config.py
git diff --check
```

Tests cover text preservation, quoting, browser error reporting, deterministic dispatch, AI failover and code execution, security confirmation, skills, native services, configuration, credentials, Telegram authorization, and UI result queues. Provider and desktop actions are mocked; successful tests do not establish live-provider connectivity.

UI tests create temporary Tk windows. Set `APPDATA` to a temporary directory to isolate preferences from a real installation.

Manual release checks should verify tray startup and exit, text commands and failures, dashboard settings, Telegram pairing with a test bot, and the frozen executable on Windows. AI models, WebView2, and external integrations require their own installed or connected environment.
