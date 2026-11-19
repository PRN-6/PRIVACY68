# PRIVACY68 // CHANNELS & USER INTERFACES

```
  ██████╗██╗  ██╗ █████╗ ███╗   ██╗███╗   ██╗███████╗██╗     ███████╗
 ██╔════╝██║  ██║██╔══██╗████╗  ██║████╗  ██║██╔════╝██║     ██╔════╝
 ██║     ███████║███████║██╔██╗ ██║██╔██╗ ██║█████╗  ██║     ███████╗
 ██║     ██╔══██║██╔══██║██║╚██╗██║██║╚██╗██║██╔══╝  ██║     ╚════██║
 ╚██████╗██║  ██║██║  ██║██║ ╚████║██║ ╚████║███████╗███████╗███████║
  ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝  ╚═══╝╚══════╝╚══════╝╚══════╝
```

PRIVACY68 provides multiple synchronized interaction channels, separating local physical interaction from remote out-of-band teleoperation.

---

## 1. Telegram Remote Gateway ([channels/telegram.py](file:///d:/projects/PRIVACY68/channels/telegram.py))

The **Telegram Remote Gateway** is PRIVACY68's primary teleoperation channel, allowing you to operate your Windows workstation from anywhere in the world over cellular networks (4G/5G) or remote Wi-Fi.

### Key Capabilities
- **Voice Note Teleoperation**: Send a voice note in Telegram; PRIVACY68 receives it, decodes the audio in memory, transcribes it via Faster-Whisper int8, executes the command on your desktop, and replies back with the result.
- **Text Commands**: Send natural language text instructions directly in chat.
- **Desktop Screenshots**: Commands requesting visual status automatically capture high-resolution desktop screenshots and upload them to Telegram.
- **Zero Port Forwarding**: Operates via long-polling the official Telegram Bot API; requires no router firewall changes, dynamic DNS, or open inbound ports.

### Security & Pairing Protocol
1. **Single-User Chat ID Lockdown**:
   - The gateway only accepts commands from the configured `TELEGRAM_ALLOWED_CHAT_ID`.
   - Any message from an unverified chat ID is rejected immediately with an audit log alert.
2. **Dynamic 6-Digit Pairing PIN**:
   - First-time setup generates a dynamic 6-digit numeric pairing PIN.
   - The user pairs their phone by sending `/pair <PIN>` to the bot.
   - Once paired, the Chat ID is persisted into `profile.json` and future interactions are authorized automatically.

### Commands Supported by the Bot
| Command | Action |
| :--- | :--- |
| `/start` | Displays gateway status, host PC info, and pairing instructions |
| `/pair <PIN>` | Authenticates and pairs the Telegram chat with the PC |
| `/unpair` | Revokes the current Telegram chat pairing |
| `/status` | Returns host CPU, RAM, active AI engine, and uptime metrics |
| `/screenshot` | Captures and sends an instant screenshot of the host PC |
| `/cancel` | Aborts any active long-running background command |
| *`<Voice Note>`* | Transcribes voice message offline and executes command |
| *`<Text Message>`* | Direct natural-language command execution |

---

## 2. Quick Command Bar ([ui/ptt_overlay.py](file:///d:/projects/PRIVACY68/ui/ptt_overlay.py))

The **Quick Command Bar** is the primary on-device interface for executing natural-language instructions on the local workstation.

### Features
- **Global Hotkey Activation**: Press **`Ctrl+Alt+Space`** from any application or full-screen game to pop up the command bar instantly.
- **Zero Microphone Dependency**: Built specifically for instant text typing with zero microphone initialization, ensuring 100% privacy and zero audio driver overhead.
- **Instant Autofocus**: The text input field is automatically focused with placeholder clearing so you can start typing immediately upon triggering.
- **Smart Dismissal**:
  - Press `Enter`: Executes the command and dismisses the bar.
  - Press `Escape`: Cancels and closes the overlay.
  - Click Outside: Automatically unfocuses and closes.
- **Aesthetic**: Minimalist translucent cyberpunk obsidian-red styling with monospace retro accents.

---

## 3. Control Center Dashboard ([ui/dashboard/](file:///d:/projects/PRIVACY68/ui/dashboard/))

The **Control Center** is a native desktop application window built with HTML5, CSS3, modern ES6, and Windows Edge Chromium via `pywebview`.

### Interface Sections
1. **Live Neural Console**:
   - Type commands with live streaming execution output, timing diagnostics, and reasoning traces.
2. **AI Brain Configuration**:
   - Live switching of LLM providers: **Google Gemini**, **Groq LPU**, **Anthropic Claude**, **OpenAI**, or **Local Ollama**.
   - Direct secure entry of API keys with one-click storage into the Windows Credential Vault.
3. **Telegram Gateway Card**:
   - Displays real-time bot connectivity, bot username, paired Chat ID, and 6-digit pairing PIN.
4. **OpenClaw Skills Drawer**:
   - Visual catalog of all installed skills (`git`, `github`, `docker`, `vscode`, `antigravity`, `browser`, `gmail`).
   - One-click inspection of skill markdown specifications and schemas.
5. **System Diagnostics**:
   - Real-time hardware health checks: CPU usage, RAM utilization, OS version, Cloud AI status, and Microphone Eavesdropping Guard status.

---

## 4. Windows System Tray ([ui/tray.py](file:///d:/projects/PRIVACY68/ui/tray.py))

Sits silently in the Windows taskbar notification area (`pystray`), ensuring PRIVACY68 runs persistently in the background:
- 📊 **Open Control Center**: Restores or focuses the Dashboard window.
- ⌨️ **Run Command (Quick Command Bar)**: Activates the `Ctrl+Alt+Space` overlay.
- 📱 **Telegram Remote Gateway**: Launches the Telegram Web interface or paired bot chat.
- ❌ **Quit PRIVACY68**: Cleanly unloads background threads and exits.

---

*Authored by PRN-6 // PRIVACY68 Channels Reference*
