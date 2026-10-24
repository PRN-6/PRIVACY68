# PRIVACY68 Voice Assistant

[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)
[![Security Policy](https://img.shields.io/badge/security-Policy-blue.svg)](SECURITY.md)
[![Contributing](https://img.shields.io/badge/contributing-Guide-orange.svg)](CONTRIBUTING.md)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Platform: Windows 10/11](https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-0078D6.svg?logo=windows&logoColor=white)](#)

PRIVACY68 is a Windows desktop voice assistant with local speech-processing components, a desktop control center, and OS automation. It uses an Agent Brain to request Python code through LiteLLM and executes returned code in a local Python subprocess.

> **Privacy and safety:** The Agent Brain currently uses the model identifier `ollama/gemma4:31b-cloud`. Do not assume that prompts are processed locally; provider routing depends on configuration. Generated Python runs with the current user's permissions. The optional mobile remote has no request authentication, so do not expose it to untrusted networks.

## Current command flow

The project does **not** currently implement a three-lane router. Pending security confirmations and short greetings are handled directly. Most other commands are sent to the Agent Brain:

```text
Voice/text input
  -> command executor
       -> pending security confirmation or greeting shortcut
       -> Agent Brain for other commands
            -> LiteLLM completion (ollama/gemma4:31b-cloud)
            -> generated Python
            -> Python subprocess (30-second timeout)
            -> result returned to the UI
```

The website's command terminal is a demonstration only. It does not connect to the desktop app or execute commands. For the full system diagrams and design details, see [PRIVACY68_SDS.md](PRIVACY68_SDS.md).

## Features

- Speech input using Faster-Whisper, with Silero VAD in the speech pipeline.
- Optional Voice Lock enrollment and speaker verification.
- Desktop dashboard for profile settings, runtime status, microphone testing, Voice Lock, command output, and plugin registry.
- Built-in Chrome, Windows System, and WhatsApp plugin classes.
- Plugin management for viewing registered entries, toggling registry state, creating a starter template, installing a Python plugin file, and uninstalling user plugins.
- Mobile remote for issuing commands over a local network when enabled.

Plugin registration is separate from command routing: the executor does not automatically dispatch requests to registered plugins. Enable/disable state is registry metadata, not a sandbox or a guarantee that generated code can only use enabled plugins. Starter templates require implementation before they perform useful automation.

## Requirements

- Windows 10 or 11 (64-bit)
- Python 3.11 or later
- Dependencies listed in [requirements.txt](requirements.txt)
- A configured LiteLLM-compatible model endpoint for Agent Brain requests
- Microphone and audio devices for voice features

GPU acceleration is optional; CPU operation may be available depending on installed dependencies and model configuration.

## Install and run

```powershell
git clone https://github.com/PRN-6/PRIVACY68.git
cd PRIVACY68
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

Set up and verify your model provider according to your deployment before sending real commands. The model identifier is currently defined in `actions/agent_brain.py`; dashboard provider settings do not override it.

## Desktop dashboard and plugins

Open the dashboard from the running application and select **Plugins** to view the local registry. User plugins are loaded from:

```text
%APPDATA%\PRIVACY68\plugins\
```

The dashboard can install `.py` plugins, create a starter template, toggle entries, and uninstall user plugins. Python plugin files execute code during loading and therefore must be treated as trusted code. Only install files you have reviewed. Built-in plugins cannot be uninstalled.

## Tests

Run the repository's unittest suite from the project root:

```powershell
python -m unittest discover tests -v
```

Tests use mocks where appropriate; passing tests does not validate real microphone hardware, model-provider availability, or generated automation on your machine.

## Documentation and contribution

- [Software Design Specification](PRIVACY68_SDS.md)
- [Project website](website/index.html)
- [Plugin guide](website/plugins.html)
- [Contributing guide](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [License](LICENSE)
