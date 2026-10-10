# Contributing to PRIVACY68 🌌

Thank you for your interest in contributing to **PRIVACY68**! We welcome contributions from developers, researchers, and open-source enthusiasts.

---

## 📜 Code of Conduct

Please treat all community members with respect and kindness. We aim to keep PRIVACY68 a safe, welcoming, and inclusive project for everyone.

---

## 🛠️ How to Contribute

### 1. Reporting Bugs
- Search existing [GitHub Issues](https://github.com/yourusername/PRIVACY68/issues) to ensure the bug hasn't already been reported.
- If not, open a new issue with a clear title, description, OS details, Python version, log tracebacks, and reproduction steps.

### 2. Suggesting Features
- Open a feature request issue describing the proposed functionality and use case.
- For new plugins or Fast Lane actions, explain how they enhance local productivity while preserving 100% privacy.

### 3. Submitting Pull Requests (PRs)
1. **Fork** the repository and clone your fork.
2. **Create a branch**:
   ```powershell
   git checkout -b feature/amazing-new-plugin
   ```
3. **Set up virtual environment**:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
4. **Run Tests**:
   Ensure all unit tests pass before submitting your PR:
   ```powershell
   pytest tests/
   ```
5. **Commit & Push**:
   Write clear, descriptive commit messages.
6. **Open a Pull Request**: Submit your PR against the `main` branch.

---

## 🔌 Writing Plugins for PRIVACY68

New plugins should be placed inside the `plugins/` directory:
- Implement clean error handling so plugin failures never crash the audio processing loop.
- Avoid introducing cloud dependencies unless strictly necessary and opt-in.
- Keep execution time fast to maintain low latency.

---

## ⚖️ License

By contributing to PRIVACY68, you agree that your contributions will be licensed under the project's [MIT License](LICENSE).
