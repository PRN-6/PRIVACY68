# Contributing to PRIVACY68

Thanks for your interest in improving PRIVACY68. Contributions should reflect the behavior of the checked-in code, preserve user safety, and include focused tests when behavior changes.

## Before opening an issue

- Search the [existing issues](https://github.com/PRN-6/PRIVACY68/issues) for duplicates.
- Include reproduction steps, Windows version, Python version, relevant logs, and the expected behavior.
- Do not post API keys, personal data, voice recordings, or other secrets. Follow [SECURITY.md](SECURITY.md) to report vulnerabilities privately.

## Development setup

PRIVACY68 currently targets Windows and Python 3.11 or later.

```powershell
git clone https://github.com/PRN-6/PRIVACY68.git
cd PRIVACY68
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Make and validate changes

1. Create a focused branch:
   ```powershell
   git checkout -b feature/short-description
   ```
2. Keep changes scoped and follow the existing style and error-reporting patterns.
3. Add or update tests for changed behavior. Avoid requiring a live model provider, microphone, or desktop automation in unit tests; mock those boundaries.
4. Run tests from the repository root:
   ```powershell
   python -m unittest discover tests -v
   ```
5. Check Python syntax and patch whitespace:
   ```powershell
   python -m compileall -q actions computer_use plugins server speech ui utils tests
   git diff --check
   ```
6. Describe the change, tests run, and any limitations in your pull request.

## Plugin contributions

- Implement plugins using the `BasePlugin` interface and provide a clear ID, name, version, and description.
- Do not treat registry enable/disable state as a security sandbox; command routing does not currently dispatch requests directly through registered plugins.
- Plugin Python code executes with the privileges of the current user. Keep side effects explicit, avoid unsafe defaults, and document network access or data handling.
- Do not claim a plugin is voice-integrated unless command routing and tests actually establish that behavior.

## Documentation and privacy claims

Update documentation alongside behavior changes. The current application does not use a three-lane command router. The Agent Brain uses `ollama/gemma4:31b-cloud` through LiteLLM, so do not claim all model processing is local or air-gapped. The optional mobile remote currently has no request authentication.

## Pull requests

- Keep pull requests focused and explain the user-visible impact.
- Link related issues where applicable.
- Include relevant test results and note any manual checks not performed.
- Do not include generated caches, virtual environments, model downloads, credentials, or unrelated files.

By contributing, you agree that your contributions are provided under the project's [MIT License](LICENSE).
