# Contributing to PRIVACY68

PRIVACY68 targets Windows and Python 3.11+. Keep changes focused, preserve typed command content, and update documentation when behavior changes.

## Development

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt .
python -m unittest discover tests -v
python -m compileall -q actions channels computer_use services skills ui utils tests app.py config.py
git diff --check
```

Mock external model APIs, network requests, and desktop actions in tests. UI tests create temporary Tk windows. For test isolation, set `APPDATA` to a temporary directory before running the suite.

## Skills and services

Declarative agent skills live in `skills/<name>/SKILL.md`; native integrations live in `services/`, and remote entry points live in `channels/`. Do not introduce audio capture or speech dependencies into these paths.

Keep all Tk widget access on the main thread. Worker threads return results through queues. Do not rewrite message text, code, paths, or search terms as part of command normalization.

## Pull requests

Describe the user-visible change, validation performed, and any limitations. Do not commit credentials, virtual environments, generated caches, or unrelated report artifacts. Follow [SECURITY.md](SECURITY.md) for vulnerability reports.
