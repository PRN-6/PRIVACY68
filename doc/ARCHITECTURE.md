# Architecture

PRIVACY68 accepts text through three entry points: `ui/command_bar.py`, the WebView dashboard, and `channels/telegram.py`. They share `actions/executor.py`.

## Command flow

1. `utils/commands.py` trims surrounding whitespace and balanced quote wrappers. It preserves punctuation, repeated words, internal whitespace, and case.
2. The executor handles pending security confirmations before other work.
3. Greetings, app launches, browser searches, window operations, virtual desktops, and supported Gmail actions use deterministic handlers.
4. Remaining requests go to `actions/agent_brain.py`, which combines model inference with skill context, code checks, subprocess execution, and bounded retries.

Browser search text retains its original case and quotes. Failed browser launches report failure instead of a successful action.

## Components

| Path | Responsibility |
| --- | --- |
| `app.py` | Startup modes and service cleanup |
| `ui/manager.py` | Hidden Tk root and tray-event queue |
| `ui/command_bar.py` | Typed input and queued execution results |
| `ui/dashboard_bridge.py` | Python API exposed to the WebView dashboard |
| `actions/` | Routing, AI execution, and learned skills |
| `computer_use/security_guard.py` | Code checks and pending confirmations |
| `services/` | Windows and Gmail integrations |
| `channels/telegram.py` | Authorized remote text input and screenshots |
| `skills/` | Declarative Markdown skill registry and resources |
| `utils/` | Preferences, credentials, and text normalization |

Workers never call Tk widgets or `after()`. The main thread polls their queues. Exiting through the tray returns from the UI loop so the application can stop the tray and Telegram worker.

The speech pipeline, recording overlay, voice settings, and audio model dependencies have been removed. System volume and media controls remain desktop actions.
