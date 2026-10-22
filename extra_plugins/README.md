# Privacy68 Extra & Community Plugins

This directory contains standalone, optional plugins that are separated from Privacy68's default built-in core.

---

## 📦 Available Extra Plugins

1. **`brave_plugin.py`** (🦁 Brave Browser)
   - Launch browser (`"open brave"`)
   - Close browser (`"close brave"`)
   - Tab controls (`"new tab in brave"`, `"close tab in brave"`, `"reopen tab in brave"`)

2. **`vscode_plugin.py`** (🧑‍💻 Visual Studio Code)
   - Launch editor (`"open vscode"`)
   - Close editor (`"close vscode"`)
   - Open integrated terminal (`"open terminal in vscode"`)
   - Quick-open files (`"find file called config.json"`)
   - Search disk for a file and open it (`"search for a file called main.py in vscode"`)


3. **`ppt_plugin.py`** (📽️ PowerPoint Control)
   - Launch / close PowerPoint
   - Start / end slideshow

4. **`notepad_plugin.py`** (📝 Notepad)
   - Launch / close Notepad
   - Type text into the active window

5. **`boilerplate_plugin.py`** (🚀 Plugin Starter Template & Boilerplate)
   - Comprehensive gold-standard boilerplate for creating custom plugins for ANY application
   - Includes metadata, action mapping, fast intents, Hermes AI descriptions, window context checking, and shortcut automation.

> **Do you need a plugin just to open an application?** No.
> PRIVACY68 indexes every application installed on the computer at startup, so
> *"open WhatsApp"*, *"open Spotify"* or *"open my editor"* work out of the box.
> A plugin is only needed for **automation** — driving an application's own
> controls (tabs, slides, dialogs, settings).

---

## 🛠️ How to Create a New App Plugin (Developer Guide)

1. **Copy the Boilerplate**:
   Make a copy of `boilerplate_plugin.py` and name it after your app (e.g. `spotify_plugin.py`).

2. **Set Plugin Metadata**:
   ```python
   id = "spotify"
   name = "Spotify"
   icon = "🎵"
   description = "Controls Spotify music playback, search, and navigation."
   ```

3. **Define Actions, Fast Intents & Descriptions**:
   - `actions`: Maps action names (e.g. `"spotify.play"`) to Python methods.
   - `fast_intents`: Training phrases for instant 0ms latency execution.
   - `descriptions`: Natural language tool descriptions used by Hermes Agent / Ollama for parameter extraction.

4. **Use Window Context Helpers**:
   - `self.is_active_window("Spotify")`: Check if your app is currently the foreground window.
   - `self.focus_window("Spotify")`: Bring the window to foreground.
   - `self.send_keys(VK_CONTROL, VK_T)`: Send keyboard shortcuts.

5. **Test Standalone**:
   Run `python my_plugin.py` directly in terminal to verify schema generation and actions.

---

## 🚀 How to Install Them into Privacy68

You can install any of these plugins in **two ways**:

### Method 1: Via the Privacy68 Control Center GUI (Recommended)
1. Open the **Privacy68 Control Center** (right-click the tray icon → **Control Center & Settings**).
2. Go to the **🛠️ Create / Install Plugin** tab.
3. Click **"📁 Browse & Install Plugin File..."** and select `extra_plugins/brave_plugin.py` or your custom plugin.
4. It will automatically install into your `%APPDATA%\PRIVACY68\plugins\` folder and hot-reload immediately!

### Method 2: Manual Copy
Copy the `.py` file directly to your User AppData folder:
```powershell
Copy-Item "extra_plugins\boilerplate_plugin.py" -Destination "$env:APPDATA\PRIVACY68\plugins\"
```
Restart or open the Control Center, and Privacy68 will automatically discover it.