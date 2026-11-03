# Security Policy & Privacy Architecture

PRIVACY68 is engineered from the ground up as a **100% local, privacy-first AI voice assistant**. Security and data isolation are core principles of the architecture.

---

## 🔒 Supported Versions

We actively release security patches and improvements for the following versions of PRIVACY68:

| Version | Supported          |
| ------- | ------------------ |
| 1.3.x   | :white_check_mark: |
| 1.2.x   | :white_check_mark: |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

---

## 🛡️ Security Architecture & Privacy Commitments

1. **Zero Background Audio Recording**
   - No continuous background listening or wake word scanning. The microphone is 100% disconnected until you click 'Click to Speak'.
   - Zero telemetry or audio recordings are stored or collected.

2. **Direct API Integration & Credential Privacy**
   - User-supplied API keys (Groq, Anthropic, OpenAI, or remote Ollama) are stored exclusively in your local `.env` and AppData folder.
   - Keys are never transmitted to any third party other than the designated API endpoint for inference.

3. **Local API & Remote Server Binding**
   - The WebSocket/HTTP bridge for the Web UI and remote commands binds only to `127.0.0.1` by default.
   - External network access requires explicit configuration and authentication keys.

4. **Action Execution Guardrails**
   - The Fast Lane and Computer Use execution modules enforce strict input sanitization to prevent shell injection or unauthorized system operations.

---

## 🚨 Reporting a Vulnerability

If you discover a potential security vulnerability or privacy bug in PRIVACY68, please report it responsibly:

1. **Do NOT open a public GitHub issue** for undisclosed security vulnerabilities.
2. **Contact via GitHub Security Advisory**: Navigate to the **Security** tab of this repository and click **"Report a vulnerability"** (Draft a private security advisory).
3. Alternatively, email the maintainers directly at `security@privacy68.local` (or submit a private security advisory).

### What to Include in Your Report
- A description of the issue and potential risk.
- Step-by-step instructions to reproduce the vulnerability (proof of concept).
- The operating system, Python version, and PRIVACY68 version used.

### Response Timeline
- **Acknowledgement**: Within 48 hours.
- **Triage & Status Update**: Within 5 business days.
- **Fix & Disclosure**: Coordinated patch release upon verification.

Thank you for helping keep PRIVACY68 safe and private for everyone!
