# Commands and interfaces

## Quick Command Bar

Start `python app.py`, then double-click the tray icon or choose **Run Command**. Type an instruction and press Enter. Escape hides the bar. Commands execute in a worker; results are displayed on the Tk main thread. A second submission is blocked while a command is running.

## Control Center

Run `python app.py --dashboard` or select **Open Dashboard** in the tray. The dashboard exposes typed commands, model configuration, skills, native services, and Telegram setup. Runtime diagnostics report the configured AI model and the Telegram worker state in that process.

## Telegram

Configure a bot token in the dashboard and start the gateway. Read the local pairing PIN and send `/pair <PIN>` in a private bot chat. The welcome message never reveals the PIN.

| Input | Result |
| --- | --- |
| Text instruction | Dispatch through the shared executor |
| `/help` | Display supported commands |
| `/status` | Model and available system metrics |
| `/screenshot` | Capture and send the desktop |
| `/unpair` | Clear chat authorization and rotate the running process's PIN |
| Audio attachment | Request typed input without downloading the attachment |

Only the configured chat can dispatch commands. Editing an old message does not execute it again. Screenshots and messages use Telegram's external service.

The background app and dashboard are separate processes. Each currently owns its own in-memory gateway state and pairing PIN. Start and pair the gateway in the same process; avoid running two pollers for the same bot token.
