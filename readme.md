# PRIVACY68 Voice Assistant

[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)
[![Security Policy](https://img.shields.io/badge/security-Policy-blue.svg)](SECURITY.md)
[![Contributing](https://img.shields.io/badge/contributing-Guide-orange.svg)](CONTRIBUTING.md)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Platform: Windows 10/11](https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-0078D6.svg?logo=windows&logoColor=white)](#)

PRIVACY68 is a Windows desktop voice assistant with local speech-processing components, a desktop control center, and OS automation. It uses an Agent Brain to request Python code through LiteLLM and executes returned code in a local Python subprocess.

**Latest Windows release:** [Download the installer from GitHub Releases](https://github.com/PRN-6/PRIVACY68/releases/latest).

> **Privacy and safety:** The Agent Brain currently uses the model identifier `ollama/gemma4:31b-cloud`. Do not assume that prompts are processed locally; provider routing depends on configuration. Generated Python runs with the current user's permissions. The optional mobile remote has no request authentication, so do not expose it to untrusted networks.

## Current command flow

The project does **not** use Open Interpreter or implement a three-lane router. Pending confirmations and greetings are handled directly. Simple Chrome and WhatsApp launch requests, plus explicit GitHub requests, are routed to their built-in plugins. Other commands go to the Agent Brain:

```text
Voice/text input
  -> command executor
       -> pending security confirmation or greeting shortcut
       -> direct Chrome / WhatsApp launch via built-in plugins
       -> GitHub plugin for explicit GitHub/Git requests
            -> GitHub API for repository, issue, and pull-request operations
            -> local Git for status, diff, and confirmed branch pushes
       -> Agent Brain for other commands
            -> LiteLLM completion (ollama/gemma4:31b-cloud)
            -> generated Python
            -> isolated subprocess (Python in source runs; executable's internal runner when frozen; 30-second timeout)
            -> result returned to the UI
```

The dashboard and voice interface share the same command executor. Chrome/WhatsApp launch and supported GitHub operations use their plugins directly; other commands need the configured Ollama service/model and are handled by the Agent Brain. The website's command terminal is a demonstration only. It does not connect to the desktop app or execute commands. For the full system diagrams and design details, see [PRIVACY68_SDS.md](PRIVACY68_SDS.md).

## Features

- Speech input using Faster-Whisper, with Silero VAD in the speech pipeline.
- Optional Voice Lock enrollment and speaker verification.
- Desktop dashboard for profile settings, runtime status, microphone testing, Voice Lock, command output, and plugin registry.
- Built-in GitHub, Chrome, Windows System, and WhatsApp plugins.
- Plugin management for viewing registered entries, toggling registry state, creating a starter template, installing a Python plugin file, and uninstalling user plugins.
- GitHub integration for checking the current repository, pushing the current branch, listing repositories/issues/pull requests, and creating issues/pull requests.
- Mobile remote for issuing commands over a local network when enabled.

The Chrome, WhatsApp, and GitHub integrations are explicitly routed by the command executor. Other plugin registrations are not automatically dispatched, and plugin enable/disable state is not a sandbox or a guarantee that generated code can only use enabled plugins. Starter templates require implementation before they perform useful automation.

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

### Build a Windows installer

For a distributable Windows build, install Inno Setup 6, create the project virtual environment, and install the project dependencies. From the repository root, run:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\build.bat
```

The build creates a PyInstaller application bundle under `dist\PRIVACY68\` and an Inno Setup installer under `installer\`. The installer provides Start Menu shortcuts for the assistant and Control Center. Build on Windows; the bundled speaker model is included, but the Agent Brain's configured LLM service/model is not bundled and may need separate configuration. The package uses WebView2 for its dashboard, which may need to be installed separately on a clean computer. The installer is currently unsigned, so Windows SmartScreen may show a warning.

## Desktop dashboard and plugins

Open the dashboard from the running application and select **Plugins** to view the local registry. User plugins are loaded from:

```text
%APPDATA%\PRIVACY68\plugins\
```

The dashboard can install `.py` plugins, create a starter template, toggle entries, and uninstall user plugins. Python plugin files execute code during loading and therefore must be treated as trusted code. Only install files you have reviewed. Built-in plugins cannot be uninstalled.

### GitHub integration

In the **Plugins** dashboard, connect a fine-grained personal access token. PRIVACY68 validates it with GitHub and stores it in Windows Credential Manager; the token is not written to project files. Grant access only to the repositories you need, with **Metadata: read**, **Contents: read/write**, **Issues: read/write**, and **Pull requests: read/write**. Use an expiration date and revoke the token from GitHub when it is no longer needed.

The dashboard command console supports explicit requests such as:

```text
check GitHub status
push my code to GitHub branch feat/my-change
list my GitHub repositories
show GitHub issues
create GitHub issue title Fix login body Login fails on startup
show pull requests on GitHub
create GitHub pull request title Add feature head feat/my-change base main
```

Branch pushes and issue/pull-request creation require confirmation. Pushes send the currently checked-out, clean branch to the existing `origin`; they do not stage or commit files, force-push, or switch branches. Review and commit changes in VS Code before asking PRIVACY68 to push. The integration supports common repository, issue, pull-request, status, and push tasks—not every GitHub API operation. GitHub requests need an internet connection.

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
